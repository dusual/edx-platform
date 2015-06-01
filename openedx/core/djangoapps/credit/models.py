# -*- coding: utf-8 -*-
"""
Models for Credit Eligibility for courses.

Credit courses allow students to receive university credit for
successful completion of a course on EdX
"""

import logging

from django.db import models

from jsonfield.fields import JSONField
from model_utils.models import TimeStampedModel
from xmodule_django.models import CourseKeyField


log = logging.getLogger(__name__)


class CreditCourse(models.Model):
    """Model for tracking a credit course."""

    course_key = CourseKeyField(max_length=255, db_index=True, unique=True)
    enabled = models.BooleanField(default=False)

    @classmethod
    def is_credit_course(cls, course_key):
        """ Check that given course is credit or not

        Args:
            course_key(CourseKey): The course identifier

        Returns:
            Bool True if the course is marked credit else False
        """
        return cls.objects.filter(course_key=course_key, enabled=True).exists()

    @classmethod
    def get_credit_course(cls, course_key):
        """ Get the credit course if exists for the given course_key

        Args:
            course_key(CourseKey): The course identifier

        Raises:
            DoesNotExist if no CreditCourse exists for the given course key.

        Returns:
            CreditCourse if one exists for the given course key.
        """
        return cls.objects.get(course_key=course_key, enabled=True)


class CreditProvider(TimeStampedModel):
    """This model represents an institution that can grant credit for a course.

    Each provider is identified by unique ID (e.g., 'ASU').
    """

    provider_id = models.CharField(max_length=255, db_index=True, unique=True)
    display_name = models.CharField(max_length=255)


class CreditRequirement(TimeStampedModel):
    """This model represents a credit requirement.

    Each requirement is uniquely identified by a `namespace` and a `name`. CreditRequirements
    also include a `criteria` dictionary, the format of which varies by the type of requirement.
    The criteria dictionary provides additional information clients may need to determine
    whether a user has satisfied the requirement.
    """

    course = models.ForeignKey(CreditCourse, related_name="credit_requirements")
    namespace = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    criteria = JSONField()
    active = models.BooleanField(default=True)

    class Meta(object):
        """Model metadata"""
        unique_together = ('namespace', 'name', 'course')

    @classmethod
    def add_or_update_course_requirement(cls, credit_course, requirement):
        """ Add requirement to a given course
        Args:
            credit_course(CreditCourse): The identifier for credit course course
            requirement(dict): requirement dict to be added

        Returns:
            (CreditRequirement, created) tuple
        """

        credit_requirement, created = cls.objects.get_or_create(
            course=credit_course,
            namespace=requirement["namespace"],
            name=requirement["name"],
            defaults={"criteria": requirement["criteria"], "active": True}
        )
        if not created:
            credit_requirement.criteria = requirement["criteria"]
            credit_requirement.active = True
            credit_requirement.save()

        return credit_requirement, created

    @classmethod
    def get_course_requirements(cls, course_key, namespace=None):
        """ Get credit requirements of a given course

        Args:
            course_key(CourseKey): The identifier for a course
            namespace(str): namespace of credit course requirements

        Returns:
            QuerySet of CreditRequirement model
        """
        requirements = CreditRequirement.objects.filter(course__course_key=course_key, active=True)
        if namespace:
            requirements = requirements.filter(namespace=namespace)
        return requirements

    @classmethod
    def disable_credit_requirements(cls, requirement_ids):
        """ Mark the given requirements inactive

        Args:
            requirement_ids(list): List of ids

        Returns:
            None
        """
        cls.objects.filter(id__in=requirement_ids).update(active=False)

    @classmethod
    def get_course_requirement(cls, course_key, namespace, name):
        """ Get credit requirement of a given course

        Args:
            course_key(CourseKey): The identifier for a course
            namespace(str): namespace of credit course requirements
            name(str): name of credit course requirement

        Returns:
            CreditRequirement object if exists
        """
        try:
            return cls.objects.get(
                course__course_key=course_key, active=True, namespace=namespace, name=name
            )
        except cls.DoesNotExist:
            return None


class CreditRequirementStatus(TimeStampedModel):
    """This model represents the status of each requirement."""

    REQUIREMENT_STATUS_CHOICES = (
        ("satisfied", "satisfied"),
    )

    username = models.CharField(max_length=255, db_index=True)
    requirement = models.ForeignKey(CreditRequirement, related_name="statuses")
    status = models.CharField(choices=REQUIREMENT_STATUS_CHOICES, max_length=32)

    @classmethod
    def add_or_update_requirement_status(cls, user_name, requirement, status="satisfied"):
        """ Add credit requirement status for given username

        Args:
            user_name(str): username of the user
            requirement(CreditRequirement): CreditRequirement object
            status(str): status of the requirement
        """
        requirement_status, created = cls.objects.get_or_create(
            username=user_name,
            requirement=requirement
        )
        if not created:
            requirement_status.status = status
            requirement_status.save()
        return requirement_status


class CreditEligibility(TimeStampedModel):
    """A record of a user's eligibility for credit from a specific credit
    provider for a specific course.
    """

    username = models.CharField(max_length=255, db_index=True)
    course = models.ForeignKey(CreditCourse, related_name="eligibilities")
    provider = models.ForeignKey(CreditProvider, related_name="eligibilities")

    class Meta(object):
        """Model metadata"""
        unique_together = ('username', 'course')
