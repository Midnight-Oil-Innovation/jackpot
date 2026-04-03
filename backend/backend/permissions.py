from enum import Enum


class PermissionGroups(str, Enum):
    """APGAP-identical role names. DO NOT rename."""

    PLATFORM_ADMIN = "Platform Admin"
    LAB_DIRECTOR = "Lab Director"
    LAB_COLLABORATOR = "Lab Collaborator"
    LAB_READER = "Lab Reader"
    BIOINFORMATICS_USER = "Bioinformatics User"
    DATA_ANALYST = "Data Analyst"
