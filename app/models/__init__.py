from .user import User
from .rbac import RoleModel, Permission, RolePermission
from .audit import AuditLog

# Phase 3 models
from .language import Language
from .user_preferences import UserPreferences
from .translation_cache import TranslationCache
from .login_event import LoginEvent
from .student_daily_activity import StudentDailyActivity

# Phase 3.1+ (Admin mgmt, overrides, notifications, API logs)
from .admin_permission_override import AdminPermissionOverride
from .notification import Notification
from .api_log import ApiCallLog
from .api_catalog_entry import ApiCatalogEntry

from .theme import Theme
from .page import Page, PageContent
from .seo_settings import SeoSettings

from .security_policy import SecurityPolicy
from .otp_challenge import OtpChallenge
from .user_security_state import UserSecurityState

from .lms import (
    Course,
    Level,
    Module,
    Lesson,
    Chapter,
    Subsection,
    Question,
    Enrollment,
    LessonProgress,
    CourseProgress,
    QuestionAttempt,
    CertificateRecord,
    PronunciationProfile,
    LearningAnalyticsSnapshot,
    CourseBatch,
    ContentVersion,
)

from .coupon import Coupon, CouponRedemption
from .payment import Payment
from .course_badge import CourseBadge

from .user_session import UserSession
from .device_preference import DevicePreference

from .translation_provider import TranslationProvider

from .speaking_topic import SpeakingTopic
from .speaking_prompt import SpeakingPrompt
from .speaking_session import SpeakingSession

from .speaking_attempt import SpeakingAttempt

from .student_reward_transaction import StudentRewardTransaction
from .reward_policy import RewardPolicy
from .economy import (
    StudentWallet,
    WalletLedgerEntry,
    CourseCoinRedemption,
    BossLevel,
    BossLevelAttempt,
    CourseChatMessage,
    CourseChatModerationEvent,
    LeaderboardRewardPolicy,
    LeaderboardRewardClaim,
)

from .speaking_provider import SpeakingProvider

from .reading_provider import ReadingProvider
from .reading_prompt_config import ReadingPromptConfig

from .reading_topic import ReadingTopic

from .reading_passage import ReadingPassage
from .reading_question import ReadingQuestion

from .reading_session_log import ReadingSessionLog

from .writing_topic import WritingTopic
from .writing_task import WritingTask
from .writing_submission import WritingSubmission

from .ai_rule_config import AIRuleConfig

from .interview_profile import InterviewProfile
from .interview_session import InterviewSession
from .interview_turn import InterviewTurn
from .interview_feedback import InterviewFeedback

from .ai_request_log import AIRequestLog
from .ai_usage_counter import AIUsageCounter

from .student_placement_result import StudentPlacementResult

from .whatsapp import WhatsAppInquiryLog
