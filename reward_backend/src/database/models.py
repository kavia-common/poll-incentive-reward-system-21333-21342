"""Database models for the Reward System backend.

Defines ORM models for Users, Polls, PollResponses, Rewards, Tokens (accumulations), and RedemptionLogs.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# PUBLIC_INTERFACE
class User(Base):
    """A user who participates in polls and receives rewards."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(256), unique=True, nullable=False, index=True)
    is_admin = Column(Boolean, default=False)
    tokens = relationship('TokenAccount', back_populates='user')
    responses = relationship('PollResponse', back_populates='user')
    redemptions = relationship('RedemptionLog', back_populates='user')
    rewards = relationship('Reward', back_populates='user')

# PUBLIC_INTERFACE
class Poll(Base):
    """A poll for which users can submit predictions/responses."""
    __tablename__ = 'polls'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    description = Column(String(1024))
    created_at = Column(DateTime, server_default=func.now())
    status = Column(String(32), default="open")  # open, closed, etc.
    results_data = Column(JSON, nullable=True)  # Actual results, once available
    weightage = Column(Float, default=1.0)
    responses = relationship('PollResponse', back_populates='poll')

# PUBLIC_INTERFACE
class PollResponse(Base):
    """User's prediction/response to a poll."""
    __tablename__ = 'poll_responses'
    __table_args__ = (UniqueConstraint('user_id', 'poll_id', name='uix_user_poll'),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    poll_id = Column(Integer, ForeignKey('polls.id'), nullable=False, index=True)
    response_data = Column(JSON)
    submitted_at = Column(DateTime, server_default=func.now())
    awarded = Column(Boolean, default=False)  # True when reward has been processed

    user = relationship('User', back_populates='responses')
    poll = relationship('Poll', back_populates='responses')
    reward = relationship('Reward', uselist=False, back_populates='poll_response')

# PUBLIC_INTERFACE
class Reward(Base):
    """A record of reward/token allocation after poll result processing."""
    __tablename__ = 'rewards'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    poll_response_id = Column(Integer, ForeignKey('poll_responses.id'), nullable=False, unique=True)
    tokens_earned = Column(Integer, nullable=False)
    awarded_at = Column(DateTime, server_default=func.now())

    user = relationship('User', back_populates='rewards')
    poll_response = relationship('PollResponse', back_populates='reward')

# PUBLIC_INTERFACE
class TokenAccount(Base):
    """Tracks user's total and available reward tokens (updated on reward or redemption)."""
    __tablename__ = 'token_accounts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    total_tokens = Column(Integer, default=0)
    available_tokens = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship('User', back_populates='tokens')

# PUBLIC_INTERFACE
class RedemptionLog(Base):
    """A record of each reward redemption attempt or completion."""
    __tablename__ = 'redemption_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    requested_at = Column(DateTime, server_default=func.now())
    tokens_redeemed = Column(Integer, nullable=False)
    status = Column(String(32), default="pending")  # pending, completed, cancelled, failed
    external_reference = Column(String(256))  # Reference to external platform/voucher API
    log_data = Column(JSON, nullable=True)    # External API response, error messages, etc.

    user = relationship('User', back_populates='redemptions')

# Indices for optimal querying
Index("ix_tokenaccount_userid", TokenAccount.user_id)
Index("ix_reward_userid", Reward.user_id)
Index("ix_redemptionlog_userid", RedemptionLog.user_id)

