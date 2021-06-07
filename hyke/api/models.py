from django.db import models
from simple_history.models import HistoricalRecords
import datetime


class ProgressStatus(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        COMPLETED = "completed"
        RESCHEDULE = "reschedule"
        SCHEDULED = "scheduled"
        SUBMITTED = "submitted"

    email = models.CharField(max_length=100, null=True)
    llcformationstatus = models.CharField(max_length=50, null=True)
    postformationstatus = models.CharField(max_length=50, null=True)
    einstatus = models.CharField(max_length=50, null=True)
    businesslicensestatus = models.CharField(max_length=50, null=True)
    bankaccountstatus = models.CharField(max_length=50, null=True)
    contributionstatus = models.CharField(max_length=50, null=True)
    SOIstatus = models.CharField(max_length=50, null=True)
    FTBstatus = models.CharField(max_length=50, null=True)
    questionnairestatus = models.CharField(max_length=50, null=True)
    bookkeepingsetupstatus = models.CharField(max_length=50, choices=Status.choices, null=True)
    taxsetupstatus = models.CharField(max_length=50, null=True)
    clientsurveystatus = models.CharField(max_length=50, null=True)
    bk_services_setup_status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PENDING
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "ProgressStatus"
        verbose_name_plural = "ProgressStatuses"

    def __str__(self):
        return f"{self.id} - {self.email}"


class StatusEngine(models.Model):
    class Status(models.IntegerChoices):
        FAILED = -4
        SECOND_RETRY = -3
        FIRST_RETRY = -2
        SCHEDULED = -1
        COMPLETED = 1
        UNNECESSARY = 4
        OFFBOARDED = 5

    class Outcome(models.TextChoices):
        SCHEDULED = "Scheduled"
        COMPLETED = "Completed"
        UNNECESSARY = "Cancelled due to Completed Task"
        OFFBOARDED = "Cancelled due to Offboarding"
        FIRST_RETRY = "Retrying previously failed"
        SECOND_RETRY = "Retrying previously failed again"
        FAILED = "Gave up retrying due to multiple failures"

    class Process(models.TextChoices):
        CLIENT_ONBOARDING_SURVEY = "Client Onboarding Survey"
        PAYMENT_ERROR_EMAIL = "Payment error email"
        RUNNING_FLOW = "Running flow"
        SCHEDULE_EMAIL = "Schedule Email"
        ANNUAL_REPORT_UPLOADED = "Annual Report Uploaded"
        ANNUAL_REPORT_REMINDER = "Annual Report Reminder"
        CALCULATE_NPS_RUNNING = "Calculate NPS Running"
        CALCULATE_NPS_ONBOARDING = "Calculate NPS Onboarding"
        KICKOFF_QUESTIONNAIRE_COMPLETED = "Kickoff Questionnaire Completed"
        KICKOFF_CALL_SCHEDULED = "Kickoff Call Scheduled"
        KICKOFF_CALL_CANCELLED = "Kickoff Call Cancelled"
        TRANSITION_PLAN_SUBMITTED = "Transition Plan Submitted"
        BK_TRAINING_CALL_SCHEDULED = "BK Training Call Scheduled"
        BK_TRAINING_CALL_CANCELLED = "BK Training Call Cancelled"
        FOLLOWUP_BK_TRAINING = "Followup - BK Training"

    class FormationType(models.TextChoices):
        HYKE_DAILY = "Hyke Daily"
        HYKE_SYSTEM = "Hyke System"
        HYKE_SALESFORCE = "Hyke Salesforce"
    class ProcessState(models.IntegerChoices):
        PENDING = 1
        COMPLETED = 2

    email = models.CharField(max_length=50, blank=True)
    process = models.CharField(max_length=100, choices=Process.choices)
    formationtype = models.CharField(max_length=20, choices=FormationType.choices, null=True)
    processstate = models.IntegerField(choices=ProcessState.choices, default=ProcessState.PENDING)
    outcome = models.IntegerField(
        choices=Status.choices, default=Status.SCHEDULED)
    data = models.CharField(max_length=1000, null=True)
    created = models.DateTimeField(auto_now_add=True)
    executed = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.id} - {self.email} - {self.process}"


class ScheduledCalendlyLogManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_canceled=False)


class CalendlyLog(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    email = models.CharField(max_length=100, null=True, db_index=True)
    phonenumber = models.CharField(max_length=100, null=True)
    slug = models.CharField(max_length=100, null=True)
    event_name = models.CharField(max_length=200, null=True)
    assignedto = models.CharField(max_length=100, null=True)
    eventtype = models.CharField(max_length=100, null=True)
    scheduledtime = models.DateTimeField(default=None, null=True, blank=True)
    is_canceled = models.BooleanField(default=False, blank=True)
    event_id = models.CharField(
        max_length=50, null=True, unique=True, db_index=True)
    data = models.CharField(max_length=10000, null=True)
    history = HistoricalRecords()
    objects = models.Manager()
    scheduled = ScheduledCalendlyLogManager()

    def __str__(self):
        pretty_print_time = datetime.strftime(
            self.scheduledtime, "%I:%M%p - %A, %B %d, %Y")
        return f"{self.id} - {self.email} - {self.slug} - {pretty_print_time}"
