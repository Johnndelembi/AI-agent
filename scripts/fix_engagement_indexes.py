"""
Script to fix MongoDB index conflicts for engagement models.

This script drops conflicting indexes and ensures proper unique indexes are created.
Run this once to fix existing index conflicts.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mongoengine import connect
from mongoengine.connection import get_db
from app.config import MONGODB_URL, logger


def fix_indexes():
    """Fix index conflicts by dropping old indexes and creating new ones."""
    try:
        # Connect to database
        connect(host=MONGODB_URL, alias='default')
        db = get_db()
        
        logger.info("Starting index fix process...")
        
        # Fix user_engagements indexes
        logger.info("Fixing user_engagements indexes...")
        try:
            db['user_engagements'].drop_index('user_id_1')
            logger.info("Dropped conflicting user_id_1 index from user_engagements")
        except Exception as e:
            logger.warning(f"Could not drop user_id_1 index (may not exist): {e}")
        
        # Fix referral_codes indexes
        logger.info("Fixing referral_codes indexes...")
        try:
            db['referral_codes'].drop_index('user_id_1')
            logger.info("Dropped conflicting user_id_1 index from referral_codes")
        except Exception as e:
            logger.warning(f"Could not drop user_id_1 index (may not exist): {e}")
        
        try:
            db['referral_codes'].drop_index('code_1')
            logger.info("Dropped conflicting code_1 index from referral_codes")
        except Exception as e:
            logger.warning(f"Could not drop code_1 index (may not exist): {e}")
        
        # Fix referrals indexes
        logger.info("Fixing referrals indexes...")
        try:
            db['referrals'].drop_index('referred_user_id_1')
            logger.info("Dropped conflicting referred_user_id_1 index from referrals")
        except Exception as e:
            logger.warning(f"Could not drop referred_user_id_1 index (may not exist): {e}")
        
        # Fix user_points indexes
        logger.info("Fixing user_points indexes...")
        try:
            db['user_points'].drop_index('user_id_1')
            logger.info("Dropped conflicting user_id_1 index from user_points")
        except Exception as e:
            logger.warning(f"Could not drop user_id_1 index (may not exist): {e}")
        
        # Now ensure proper indexes are created by importing models
        logger.info("Creating proper indexes...")
        from app.models.engagement import (
            UserEngagement, ReferralCode, Referral, UserPoints
        )
        
        # Ensure indexes (this will create the properly named indexes)
        try:
            UserEngagement.ensure_indexes()
            logger.info("✓ UserEngagement indexes ensured")
        except Exception as e:
            logger.warning(f"Could not ensure UserEngagement indexes: {e}")
        
        try:
            ReferralCode.ensure_indexes()
            logger.info("✓ ReferralCode indexes ensured")
        except Exception as e:
            logger.warning(f"Could not ensure ReferralCode indexes: {e}")
        
        try:
            Referral.ensure_indexes()
            logger.info("✓ Referral indexes ensured")
        except Exception as e:
            logger.warning(f"Could not ensure Referral indexes: {e}")
        
        try:
            UserPoints.ensure_indexes()
            logger.info("✓ UserPoints indexes ensured")
        except Exception as e:
            logger.warning(f"Could not ensure UserPoints indexes: {e}")
        
        logger.info("✓ Index fix process completed successfully!")
        
    except Exception as e:
        logger.error(f"Error fixing indexes: {e}")
        raise


if __name__ == "__main__":
    fix_indexes()

