from app.models.profile_patch import LivingProfilePatch
from app.services.profile_manager import profile_manager

profile = profile_manager.merge(
    "demo",
    LivingProfilePatch(
        work_location="南山科技园",
        budget=6000,
    ),
)

print(profile)

profile = profile_manager.merge(
    "demo",
    LivingProfilePatch(
        commute_minutes=30,
    ),
)

print(profile)
