"""
Recommendation engine service layer powered by SQLAlchemy and Supabase-mirrored ORM models.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union, Callable
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import and_, case, desc, func, literal, select, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


from src.config import MIPANGO_DATABASE, logger
from src.schemas.recommendation import (
    User,
    Cycle,
    UserCycle,
    CycleContribution,
    UserCycleGoal,
    CycleParticipantSlot,
    Payment,
    PayoutTable
)


class RecommendationServiceError(Exception):
    """Raised when the recommendation service cannot complete a request."""


@dataclass(frozen=True)
class RecommendationModels:
    """
    Container for ORM models used by the recommendation engine.
    """

    user: type
    cycle: type
    user_cycle: type
    cycle_contribution: type
    user_cycle_goal: type
    payout: Optional[type] = None
    payment: Optional[type] = None
    cycle_participant_slot: Optional[type] = None


DEFAULT_RECOMMENDATION_MODELS = RecommendationModels(
    user=User,
    cycle=Cycle,
    user_cycle=UserCycle,
    cycle_contribution=CycleContribution,
    user_cycle_goal=UserCycleGoal,
    payout=PayoutTable,
    payment=Payment,
    cycle_participant_slot=CycleParticipantSlot,
)


@dataclass(frozen=True)
class CycleRecommendation:
    """Structured recommendation output for a single cycle."""

    cycle_id: int
    cycle_name: str
    score: float
    reason: str
    supporters: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecommendationBundle:
    """Grouped recommendation response."""

    personalized: List[CycleRecommendation] = field(default_factory=list)
    popular: List[CycleRecommendation] = field(default_factory=list)


class RecommendationService:
    """
    Service layer responsible for producing cycle recommendations.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        models: RecommendationModels,
        goal_weight: float = 0.7,
        cycle_overlap_weight: float = 0.3,
    ):
        if goal_weight < 0 or cycle_overlap_weight < 0:
            raise ValueError("Recommendation weights must be non-negative")
        if goal_weight == 0 and cycle_overlap_weight == 0:
            raise ValueError("At least one recommendation weight must be positive")

        self._session_factory = session_factory
        self.models = models
        self.goal_weight = goal_weight
        self.cycle_overlap_weight = cycle_overlap_weight

    @contextmanager
    def _session_scope(self) -> Session:
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    @staticmethod
    def _normalize_user_id(user_id: Union[str, UUID]) -> Union[str, UUID]:
        if isinstance(user_id, UUID):
            return user_id
        return str(user_id)

    def get_personalized_cycle_recommendations(
        self,
        user_id: Union[str, UUID],
        limit: int = 5,
    ) -> List[CycleRecommendation]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        normalized_user_id = self._normalize_user_id(user_id)

        with self._session_scope() as session:
            try:
                goal_ids = self._fetch_user_goal_ids(session, normalized_user_id)
                joined_cycle_ids = self._fetch_user_cycle_ids(session, normalized_user_id)

                if not goal_ids and not joined_cycle_ids:
                    logger.info(
                        "No historical data for user %s; skipping personalized recommendations",
                        normalized_user_id,
                    )
                    return []

                similarity_subquery = self._build_similarity_subquery(
                    normalized_user_id,
                    goal_ids,
                    joined_cycle_ids,
                )

                if similarity_subquery is None:
                    logger.info("Unable to build similarity data for user %s", normalized_user_id)
                    return []

                cycle_model = self.models.cycle
                user_cycle_model = self.models.user_cycle

                stmt = (
                    select(
                        cycle_model.id.label("cycle_id"),
                        cycle_model.cycle_name.label("cycle_name"),
                        func.sum(similarity_subquery.c.score).label("score"),
                        func.count(similarity_subquery.c.user_id).label("supporters"),
                        func.avg(similarity_subquery.c.goal_matches).label("avg_goal_matches"),
                        func.avg(similarity_subquery.c.cycle_matches).label("avg_cycle_matches"),
                    )
                    .join(user_cycle_model, user_cycle_model.cycle_id == cycle_model.id)
                    .join(similarity_subquery, similarity_subquery.c.user_id == user_cycle_model.user_id)
                    .group_by(cycle_model.id, cycle_model.cycle_name)
                    .order_by(desc("score"), desc("supporters"))
                    .limit(limit)
                )

                if joined_cycle_ids:
                    stmt = stmt.where(~cycle_model.id.in_(joined_cycle_ids))

                rows = session.execute(stmt).all()

                recommendations: List[CycleRecommendation] = []
                for row in rows:
                    metrics = {
                        "avg_goal_matches": float(row.avg_goal_matches or 0),
                        "avg_cycle_matches": float(row.avg_cycle_matches or 0),
                    }
                    reason_parts = []
                    if metrics["avg_goal_matches"]:
                        reason_parts.append(f"shared goals score {metrics['avg_goal_matches']:.2f}")
                    if metrics["avg_cycle_matches"]:
                        reason_parts.append(f"cycle overlap score {metrics['avg_cycle_matches']:.2f}")
                    reason = "; ".join(reason_parts) if reason_parts else "Similar users joined this cycle"

                    recommendations.append(
                        CycleRecommendation(
                            cycle_id=row.cycle_id,
                            cycle_name=row.cycle_name,
                            score=float(row.score or 0),
                            supporters=int(row.supporters or 0),
                            reason=reason,
                            metrics=metrics,
                        )
                    )

                return recommendations
            except SQLAlchemyError as exc:
                logger.error(
                    "Failed to compute personalized recommendations for user %s: %s",
                    normalized_user_id,
                    exc,
                )
                raise RecommendationServiceError("Failed to compute personalized recommendations") from exc

    def get_popular_cycle_recommendations(
        self,
        limit: int = 5,
        min_participants: int = 1,
    ) -> List[CycleRecommendation]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if min_participants < 0:
            raise ValueError("min_participants cannot be negative")

        cycle_model = self.models.cycle
        user_cycle_model = self.models.user_cycle
        payout_model = self.models.payout
        payment_model = self.models.payment
        contribution_model = self.models.cycle_contribution

        with self._session_scope() as session:
            try:
                participants_expr = (
                    select(func.count(func.distinct(user_cycle_model.user_id)))
                    .where(user_cycle_model.cycle_id == cycle_model.id)
                    .scalar_subquery()
                )

                payout_rate_expr = None
                if payout_model is not None:
                    payout_rate_expr = (
                        select(
                            func.avg(
                                case(
                                    (payout_model.payout_status == "success", 1),
                                    else_=0,
                                )
                            )
                        )
                        .where(payout_model.cycle_id == cycle_model.id)
                        .scalar_subquery()
                    )

                avg_contribution_expr = None
                if payment_model is not None:
                    avg_contribution_expr = (
                        select(func.avg(payment_model.amount))
                        .where(
                            and_(
                                payment_model.cycle_id == cycle_model.id,
                                payment_model.payment_type.in_(["contribution", "deposit"]),
                                payment_model.payment_status.in_(["completed", "success"]),
                            )
                        )
                        .scalar_subquery()
                    )

                avg_seats_expr = None
                if contribution_model is not None:
                    avg_seats_expr = (
                        select(func.avg(contribution_model.number_of_seats))
                        .where(contribution_model.cycle_id == cycle_model.id)
                        .scalar_subquery()
                    )

                score_components: List[Any] = []
                score_components.append(func.coalesce(participants_expr, 0) * literal(0.5))
                if payout_rate_expr is not None:
                    score_components.append(func.coalesce(payout_rate_expr, 0) * literal(0.25))
                if avg_contribution_expr is not None:
                    score_components.append(func.coalesce(avg_contribution_expr, 0) * literal(0.15))
                if avg_seats_expr is not None:
                    score_components.append(func.coalesce(avg_seats_expr, 0) * literal(0.1))

                blended_score = score_components[0]
                for component in score_components[1:]:
                    blended_score = blended_score + component

                stmt = (
                    select(
                        cycle_model.id.label("cycle_id"),
                        cycle_model.cycle_name.label("cycle_name"),
                        participants_expr.label("participants"),
                        (payout_rate_expr if payout_rate_expr is not None else literal(None)).label("payout_success_rate"),
                        (avg_contribution_expr if avg_contribution_expr is not None else literal(None)).label("avg_contribution"),
                        (avg_seats_expr if avg_seats_expr is not None else literal(None)).label("avg_seats"),
                        blended_score.label("score"),
                    )
                    .where(cycle_model.cycle_status.in_(["active", "open"]))
                    .order_by(desc("score"), desc(participants_expr))
                    .limit(limit)
                )

                if min_participants > 0:
                    stmt = stmt.where(participants_expr >= min_participants)

                rows = session.execute(stmt).all()

                recommendations: List[CycleRecommendation] = []
                for row in rows:
                    participants = int(row.participants or 0)
                    payout_success = (
                        float(row.payout_success_rate) if row.payout_success_rate is not None else None
                    )
                    avg_contribution = (
                        float(row.avg_contribution) if row.avg_contribution is not None else None
                    )
                    avg_seats = float(row.avg_seats) if row.avg_seats is not None else None

                    metrics: Dict[str, Any] = {
                        "participants": participants,
                    }
                    if payout_success is not None:
                        metrics["payout_success_rate"] = payout_success
                    if avg_contribution is not None:
                        metrics["avg_contribution"] = avg_contribution
                    if avg_seats is not None:
                        metrics["avg_seats"] = avg_seats

                    reason_parts = [f"{participants} participants"]
                    if payout_success is not None:
                        reason_parts.append(f"{payout_success * 100:.0f}% payout success")
                    if avg_contribution is not None:
                        reason_parts.append(f"avg contribution {avg_contribution:.2f}")
                    if avg_seats is not None:
                        reason_parts.append(f"avg seats {avg_seats:.2f}")

                    reason = ", ".join(reason_parts)

                    recommendations.append(
                        CycleRecommendation(
                            cycle_id=row.cycle_id,
                            cycle_name=row.cycle_name,
                            score=float(row.score or 0),
                            supporters=participants,
                            reason=reason,
                            metrics=metrics,
                        )
                    )

                return recommendations
            except SQLAlchemyError as exc:
                logger.error("Failed to compute popular cycle recommendations: %s", exc)
                raise RecommendationServiceError("Failed to compute popular cycle recommendations") from exc

    def recommend_for_user(
        self,
        user_id: Union[str, UUID],
        personalized_limit: int = 5,
        popular_limit: int = 5,
        min_popular_participants: int = 1,
    ) -> RecommendationBundle:
        personalized = self.get_personalized_cycle_recommendations(
            user_id=user_id,
            limit=personalized_limit,
        )

        popular = self.get_popular_cycle_recommendations(
            limit=popular_limit,
            min_participants=min_popular_participants,
        )

        return RecommendationBundle(
            personalized=personalized,
            popular=popular,
        )

    def _fetch_user_goal_ids(
        self,
        session: Session,
        user_id: Union[str, UUID],
    ) -> List[Any]:
        goal_model = self.models.user_cycle_goal
        stmt = select(goal_model.goal_id).where(goal_model.user_id == user_id)
        return list({goal_id for goal_id in session.scalars(stmt)})

    def _fetch_user_cycle_ids(
        self,
        session: Session,
        user_id: Union[str, UUID],
    ) -> List[Any]:
        user_cycle_model = self.models.user_cycle
        stmt = select(user_cycle_model.cycle_id).where(user_cycle_model.user_id == user_id)
        return list({cycle_id for cycle_id in session.scalars(stmt)})

    def _build_similarity_subquery(
        self,
        user_id: Union[str, UUID],
        goal_ids: Sequence[Any],
        cycle_ids: Sequence[Any],
    ):
        goal_model = self.models.user_cycle_goal
        user_cycle_model = self.models.user_cycle

        goal_stmt = None
        if goal_ids:
            goal_stmt = (
                select(
                    goal_model.user_id.label("user_id"),
                    func.count(goal_model.goal_id).label("goal_matches"),
                )
                .where(goal_model.goal_id.in_(goal_ids))
                .where(goal_model.user_id != user_id)
                .group_by(goal_model.user_id)
                .subquery()
            )

        cycle_stmt = None
        if cycle_ids:
            cycle_stmt = (
                select(
                    user_cycle_model.user_id.label("user_id"),
                    func.count(func.distinct(user_cycle_model.cycle_id)).label("cycle_matches"),
                )
                .where(user_cycle_model.cycle_id.in_(cycle_ids))
                .where(user_cycle_model.user_id != user_id)
                .group_by(user_cycle_model.user_id)
                .subquery()
            )

        if goal_stmt is None and cycle_stmt is None:
            return None

        if goal_stmt is not None and cycle_stmt is not None:
            score_expr = (
                func.coalesce(goal_stmt.c.goal_matches, 0) * literal(self.goal_weight)
                + func.coalesce(cycle_stmt.c.cycle_matches, 0) * literal(self.cycle_overlap_weight)
            )

            return (
                select(
                    func.coalesce(goal_stmt.c.user_id, cycle_stmt.c.user_id).label("user_id"),
                    score_expr.label("score"),
                    func.coalesce(goal_stmt.c.goal_matches, 0).label("goal_matches"),
                    func.coalesce(cycle_stmt.c.cycle_matches, 0).label("cycle_matches"),
                )
                .select_from(goal_stmt.outerjoin(cycle_stmt, goal_stmt.c.user_id == cycle_stmt.c.user_id))
                .subquery()
            )

        if goal_stmt is not None:
            return (
                select(
                    goal_stmt.c.user_id,
                    (goal_stmt.c.goal_matches * literal(self.goal_weight)).label("score"),
                    goal_stmt.c.goal_matches.label("goal_matches"),
                    literal(0).label("cycle_matches"),
                )
                .select_from(goal_stmt)
                .subquery()
            )

        return (
            select(
                cycle_stmt.c.user_id,
                (cycle_stmt.c.cycle_matches * literal(self.cycle_overlap_weight)).label("score"),
                literal(0).label("goal_matches"),
                cycle_stmt.c.cycle_matches.label("cycle_matches"),
            )
            .select_from(cycle_stmt)
            .subquery()
        )


def create_recommendation_service(
    models: RecommendationModels,
    database_url: Optional[str] = None,
    goal_weight: float = 0.7,
    cycle_overlap_weight: float = 0.3,
) -> Optional[RecommendationService]:
    db_url = database_url or MIPANGO_DATABASE

    if not db_url:
        logger.warning("MIPANGO_DATABASE not configured - recommendation service unavailable")
        return None

    try:
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            echo=False,
        )

        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )

        service = RecommendationService(
            session_factory=SessionLocal,
            models=models,
            goal_weight=goal_weight,
            cycle_overlap_weight=cycle_overlap_weight,
        )

        logger.info("RecommendationService initialized successfully with MIPANGO_DATABASE")
        return service

    except Exception as e:
        logger.error(f"Failed to initialize RecommendationService: {e}")
        return None


_service: Optional[RecommendationService] = None


def set_recommendation_service(service: Optional[RecommendationService]) -> None:
    global _service
    _service = service


def recommendation_service_available() -> bool:
    return _service is not None


@tool
def get_personalized_cycle_recommendations(user_id: str, limit: int = 5) -> str:
    """Return tailored ROSCA cycle suggestions for the specified user."""
    if not _service:
        return "❌ Recommendation service is not available. Please configure the recommendation service to use this tool."

    try:
        recommendations = _service.get_personalized_cycle_recommendations(
            user_id=user_id,
            limit=limit,
        )

        if not recommendations:
            return f"📋 No personalized recommendations found for user {user_id}. This user may be new or have no similar users in the system."

        result_lines = [f"🎯 Personalized Cycle Recommendations for User {user_id}:\n"]
        for i, rec in enumerate(recommendations, 1):
            result_lines.append(
                f"{i}. **{rec.cycle_name}** (ID: {rec.cycle_id})\n"
                f"   - Score: {rec.score:.2f}\n"
                f"   - Reason: {rec.reason}\n"
                f"   - Supported by {rec.supporters} similar users"
            )

        return "\n".join(result_lines)
    except RecommendationServiceError as e:
        return f"❌ Error getting personalized recommendations: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in personalized recommendations tool: {e}")
        return f"❌ An unexpected error occurred: {str(e)}"


@tool
def get_popular_cycle_recommendations(limit: int = 5, min_participants: int = 1) -> str:
    """Return the top community cycles ranked by popularity and performance."""
    if not _service:
        return "❌ Recommendation service is not available. Please configure the recommendation service to use this tool."

    try:
        recommendations = _service.get_popular_cycle_recommendations(
            limit=limit,
            min_participants=min_participants,
        )

        if not recommendations:
            return f"📋 No popular cycles found matching the criteria (min_participants={min_participants})."

        result_lines = [f"🔥 Popular Cycle Recommendations:\n"]
        for i, rec in enumerate(recommendations, 1):
            metrics_str = ", ".join([f"{k}: {v}" for k, v in rec.metrics.items()])
            result_lines.append(
                f"{i}. **{rec.cycle_name}** (ID: {rec.cycle_id})\n"
                f"   - Score: {rec.score:.2f}\n"
                f"   - {rec.reason}\n"
                f"   - Metrics: {metrics_str}"
            )

        return "\n".join(result_lines)
    except RecommendationServiceError as e:
        return f"❌ Error getting popular recommendations: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in popular recommendations tool: {e}")
        return f"❌ An unexpected error occurred: {str(e)}"


def get_recommendation_tools() -> List[Any]:
    return [
        get_personalized_cycle_recommendations,
        get_popular_cycle_recommendations,
    ]


__all__ = [
    "RecommendationServiceError",
    "RecommendationModels",
    "DEFAULT_RECOMMENDATION_MODELS",
    "CycleRecommendation",
    "RecommendationBundle",
    "RecommendationService",
    "create_recommendation_service",
    "set_recommendation_service",
    "recommendation_service_available",
    "get_recommendation_tools",
]

