"""
SQLAlchemy ORM models that mirror the Supabase schema used by the recommendation engine.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    BigInteger,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True)
    created_at = Column(DateTime)
    full_name = Column(Text)
    location = Column(Text)
    profile_url = Column(Text)
    nida_no = Column(Text)
    email = Column(Text)
    phone = Column(Text)
    salary_amount = Column(Numeric)
    job = Column(Text)
    fcm_token = Column(Text)
    gender = Column(String)
    is_deletion = Column(Boolean)
    deletion_request_date = Column(DateTime)
    deletion_completion_date = Column(DateTime)
    seen_on_cycle = Column(Boolean)
    is_bot = Column(Boolean)


class ContributionPlan(Base):
    __tablename__ = "contribution_plans"

    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime)
    contribution_amount = Column(Integer)
    admin_fee = Column(Integer)
    frequency = Column(SmallInteger)
    period_days = Column(SmallInteger)
    total_players_capacity = Column(Integer)
    payout_per_recipient = Column(Numeric)
    total_circle_contribution = Column(Numeric)
    total_admin_fees_all = Column(Numeric)
    total_player_contribution_amount = Column(Numeric)
    admin_number = Column(SmallInteger)


class Cycle(Base):
    __tablename__ = "cycles"

    id = Column(Integer, primary_key=True)
    contribution_plan_id = Column(BigInteger, ForeignKey("contribution_plans.id"))
    start_date = Column(Date)
    end_date = Column(Date)
    cycle_status = Column(String)
    current_enrolled_participants = Column(Numeric)
    next_contribution_date = Column(Date)
    cycle_name = Column(Text)
    is_auto_generated = Column(Boolean)


class UserCycle(Base):
    __tablename__ = "user_cycles"

    id = Column(BigInteger, primary_key=True)
    cycle_id = Column(BigInteger, ForeignKey("cycles.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_completed = Column(Boolean)
    joined_at = Column(DateTime)
    contribution_amount = Column(Numeric)


class CycleContribution(Base):
    __tablename__ = "cycle_contributions"

    id = Column(BigInteger, primary_key=True)
    cycle_id = Column(Integer, ForeignKey("cycles.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime)
    payment_id = Column(BigInteger)
    number_of_seats = Column(Integer)


class CycleGoalsOption(Base):
    __tablename__ = "cycle_goals_options"

    id = Column(BigInteger, primary_key=True)
    name = Column(Text)
    icon = Column(JSONB)
    created_at = Column(DateTime)


class UserCycleGoal(Base):
    __tablename__ = "user_cycle_goals"

    id = Column(BigInteger, primary_key=True)
    userid = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    cycle_id = Column(Integer, ForeignKey("cycles.id"))
    goal_id = Column(BigInteger, ForeignKey("cycle_goals_options.id"))
    created_at = Column(DateTime)


class CycleParticipantSlot(Base):
    __tablename__ = "cycle_participant_slots"

    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime)
    cycle_id = Column(Integer, ForeignKey("cycles.id"))
    payout_date = Column(Date)
    slot_status = Column(String)
    seat_capacity = Column(Integer)
    user_ids = Column(ARRAY(UUID(as_uuid=True)))
    participants_ids = Column(ARRAY(Integer))


class Payment(Base):
    __tablename__ = "payments"

    id = Column(BigInteger, primary_key=True)
    cycle_id = Column(BigInteger)
    created_at = Column(DateTime)
    user_id = Column(UUID(as_uuid=True))
    payment_method_id = Column(BigInteger)
    payment_amount = Column(Numeric)
    payment_status = Column(String)
    is_contribution = Column(Boolean)
    is_payout = Column(Boolean)
    referenceNumber = Column(Text)
    updated_at = Column(DateTime)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(BigInteger, primary_key=True)
    name = Column(Text)
    credentials = Column(JSONB)
    created_at = Column(DateTime)
    procedures = Column(JSONB)


class UserWallet(Base):
    __tablename__ = "user_wallet"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    created_at = Column(DateTime)
    payment_number = Column(Text)
    payment_method_id = Column(Integer)


class PayoutTable(Base):
    __tablename__ = "payouts_table"

    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime)
    payout_date = Column(Date)
    payout_amount = Column(Float)
    payout_number = Column(Text)
    payment_id = Column(BigInteger)
    cycle_participant_slot_id = Column(BigInteger)
    user_id = Column(UUID(as_uuid=True))
    cycle_id = Column(Integer)
    payout_status = Column(String)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True)
    receiver_id = Column(UUID(as_uuid=True))
    body = Column(JSONB)
    type = Column(String)
    created_at = Column(DateTime)
    is_read = Column(Boolean)
    updated_at = Column(DateTime)


class UserGuarantor(Base):
    __tablename__ = "user_guarantor"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(UUID(as_uuid=True))
    first_name = Column(Text)
    last_name = Column(Text)
    nida_no = Column(Text)
    phone_no = Column(Text)
    location = Column(Text)
    created_at = Column(DateTime)


class UserOnlinePrecense(Base):
    __tablename__ = "user_online_precense"

    id = Column(BigInteger, primary_key=True)
    userid = Column(UUID(as_uuid=True))
    is_online = Column(Boolean)
    last_seen = Column(DateTime)
    created_at = Column(DateTime)


class PaymentReferenceLog(Base):
    __tablename__ = "payment_reference_log"

    id = Column(BigInteger, primary_key=True)
    reference_number = Column(Text)
    created_at = Column(DateTime)


class PendingPaymentsJobs(Base):
    __tablename__ = "pending_payments_jobs"

    payment_id = Column(BigInteger, primary_key=True)
    job_id = Column(Integer)
    scheduled_at = Column(DateTime)


__all__ = [
    "Base",
    "User",
    "ContributionPlan",
    "Cycle",
    "UserCycle",
    "CycleContribution",
    "CycleGoalsOption",
    "UserCycleGoal",
    "CycleParticipantSlot",
    "Payment",
    "PaymentMethod",
    "UserWallet",
    "PayoutTable",
    "Notification",
    "UserGuarantor",
    "UserOnlinePrecense",
    "PaymentReferenceLog",
    "PendingPaymentsJobs",
]

