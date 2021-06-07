from dateutil.relativedelta import relativedelta
from django import db
from django.db.models import Q
from django.utils import timezone
from hyke.api.models import (
    ProgressStatus,
    StatusEngine,
)
from hyke.automation.jobs import (
    nps_calculator_onboarding,
    nps_calculator_running,
)
from hyke.email.jobs import send_transactional_email
from hyke.fms.jobs import create_dropbox_folders
from hyke.scheduled.base import next_annualreport_reminder
from hyke.scheduled.service.nps_surveys import (
    schedule_next_running_survey_sequence,
    schedule_onboarding_survey_sequence,
    send_client_onboarding_survey,
)
from structlog import get_logger

logger = get_logger(__name__)


class ProcessFactory:
    def __init__(self):
        self.processes = {}

    def register_new_process(self, key_, func_):
        self.processes[key_] = func_

    def process_run(self, key_, *args, **kwargs):
        if key_ not in self.processes:
            raise NotImplementedError()

        self.processes[key_](*args, **kwargs)


process_factory = ProcessFactory()


def process_client_onboarding_survey(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    if item.process == StatusEngine.Process.CLIENT_ONBOARDING_SURVEY:
        try:
            send_client_onboarding_survey(email=item.email)
        except Exception as e:
            logger.exception(
                f"Can't process Onboarding NPS Survey for status engine id={item.id}")


process_factory.register_new_process(
    StatusEngine.Process.CLIENT_ONBOARDING_SURVEY, process_client_onboarding_survey)


def process_payment_error_email(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    try:
        send_transactional_email(
            email=item.email, template="[Action required] - Please update your payment information",
        )
        print("[Action required] - Please update your payment information email is sent to " + item.email)
    except Exception as e:
        logger.exception(
            f"Can't send payment error email to {item.email}")

process_factory.register_new_process(
    StatusEngine.Process.PAYMENT_ERROR_EMAIL, process_payment_error_email)


def process_running_flow(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    try:
        ps = ProgressStatus.objects.get(email__iexact=item.email)
        ps.bookkeepingsetupstatus = ProgressStatus.Status.COMPLETED
        ps.taxsetupstatus = "completed2"
        ps.save()
    except ProgressStatus.DoesNotExist:
        logger.exception(
            f"Can't find a progress status for email = {item.email}")
        return

    StatusEngine.objects.get_or_create(
        email=item.email,
        processstate=item.processstate,
        outcome=item.outcome,
        process=StatusEngine.Process.SCHEDULE_EMAIL,
        formationtype=StatusEngine.FormationType.HYKE_DAILY,
        data="What's upcoming with Collective?",
        defaults={"executed": timezone.now() + relativedelta(days=1)},
    )

    StatusEngine.objects.get_or_create(
        email=item.email,
        process=StatusEngine.Process.RUNNING_FLOW,
        formationtype=StatusEngine.FormationType.HYKE_SYSTEM,
        processstate=StatusEngine.ProcessState.COMPLETED,
    )

    schedule_onboarding_survey_sequence(email=item.email)
    schedule_next_running_survey_sequence(email=item.email)

    create_dropbox_folders(email=item.email)

    print("Dropbox folders are created for " + item.email)

    has_run_before = StatusEngine.objects.filter(
        email=item.email, process=item.process, processstate=item.processstate, outcome=StatusEngine.Status.COMPLETED,
    ).exists()

    if has_run_before:
        print(
            "Not creating form w9 or emailing pops because dropbox folders job has already run for {}".format(
                item.email
            )
        )


process_factory.register_new_process(
    StatusEngine.Process.RUNNING_FLOW, process_running_flow)


def process_annual_report_uploaded(item):
    reportdetails = item.data.split("---")
    reportname = reportdetails[1].strip()
    reportyear = reportdetails[0].strip()
    reportstate = reportdetails[2].strip() if len(reportdetails) == 3 else None

    data_filter = Q(data=f"{reportyear} --- {reportname}")
    if reportstate:
        data_filter |= Q(
            data=f"{reportyear} --- {reportname} --- {reportstate}")

    SEs = StatusEngine.objects.filter(email=item.email, process=StatusEngine.Process.ANNUAL_REPORT_REMINDER, outcome=item.outcome).filter(
        data_filter
    )
    for se in SEs:
        se.outcome = StatusEngine.Status.COMPLETED
        se.executed = timezone.now()
        se.save()

    # complete this before we schedule the next reminder
    item.outcome = StatusEngine.Status.COMPLETED
    item.executed = timezone.now()
    item.save()

    next_annualreport_reminder(item.email, reportname, reportstate)


process_factory.register_new_process(
    StatusEngine.Process.ANNUAL_REPORT_UPLOADED, process_annual_report_uploaded)


def process_calculate_nps_running(item):
    nps_calculator_running()

    print("Running NPS is calculated for " + item.data)


process_factory.register_new_process(
    StatusEngine.Process.CALCULATE_NPS_RUNNING, process_calculate_nps_running)


def process_calculate_nps_onboarding(item):
    nps_calculator_onboarding()

    print("Onboarding NPS is calculated for " + item.data)


process_factory.register_new_process(
    StatusEngine.Process.CALCULATE_NPS_ONBOARDING, process_calculate_nps_onboarding)


def process_kickoff_questionnaire_completed(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    try:
        progress_status = ProgressStatus.objects.get(email__iexact=item.email)
        progress_status.questionnairestatus = ProgressStatus.Status.SCHEDULED
        progress_status.save()
    except ProgressStatus.DoesNotExist:
        logger.exception(
            f"Can't find a progress status for email = {item.email}")
        return

    StatusEngine.objects.create(
        email=item.email,
        processstate=item.processstate,
        outcome=item.outcome,
        process=item.process,
        data=item.data,
        formationtype=StatusEngine.Process.HYKE_SALESFORCE,
    )


process_factory.register_new_process(
    StatusEngine.Process.KICKOFF_QUESTIONNAIRE_COMPLETED, process_kickoff_questionnaire_completed)


def process_kickoff_call_scheduled(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    try:
        progress_status = ProgressStatus.objects.get(email__iexact=item.email)
        progress_status.questionnairestatus = ProgressStatus.Status.SCHEDULED
        progress_status.save()
    except ProgressStatus.DoesNotExist:
        logger.exception(
            f"Can't find a progress status for email = {item.email}")
        return

    StatusEngine.objects.create(
        email=item.email,
        processstate=item.processstate,
        outcome=item.outcome,
        process=item.process,
        data=item.data,
        formationtype=StatusEngine.Process.HYKE_SALESFORCE,
    )


process_factory.register_new_process(
    StatusEngine.Process.KICKOFF_CALL_SCHEDULED, process_kickoff_call_scheduled)


def process_kickoff_call_cancelled(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    try:
        progress_status = ProgressStatus.objects.get(email__iexact=item.email)
        progress_status.questionnairestatus = ProgressStatus.Status.RESCHEDULE
        progress_status.save()
    except ProgressStatus.DoesNotExist:
        logger.exception(
            f"Can't find a progress status for email = {item.email}")
        return

    StatusEngine.objects.create(
        email=item.email,
        processstate=item.processstate,
        outcome=item.outcome,
        process=item.process,
        formationtype=StatusEngine.Process.HYKE_SALESFORCE,
    )


process_factory.register_new_process(
    StatusEngine.Process.KICKOFF_CALL_CANCELLED, process_kickoff_call_cancelled)


def process_transition_plan_submitted(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    try:
        progress_status = ProgressStatus.objects.get(email__iexact=item.email)
        progress_status.questionnairestatus = ProgressStatus.Status.SUBMITTED
        progress_status.save()
    except ProgressStatus.DoesNotExist:
        logger.exception(
            f"Can't find a progress status for email = {item.email}")
        return

    StatusEngine.objects.create(
        email=item.email,
        process=item.process,
        processstate=item.processstate,
        outcome=item.outcome,
        formationtype=StatusEngine.Process.HYKE_SALESFORCE,
    )

    StatusEngine.objects.get_or_create(
        email=item.email,
        processstate=item.processstate,
        outcome=item.outcome,
        process=StatusEngine.Process.SCHEDULE_EMAIL,
        formationtype=StatusEngine.FormationType.HYKE_DAILY,
        data="Welcome to the Collective community!",
        defaults={"executed": timezone.now() + relativedelta(days=1)},
    )


process_factory.register_new_process(
    StatusEngine.Process.TRANSITION_PLAN_SUBMITTED, process_transition_plan_submitted)


def process_bk_training_call_scheduled(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    StatusEngine.objects.create(
        email=item.email,
        processstate=item.processstate,
        outcome=item.outcome,
        process=item.process,
        data=item.data,
        formationtype=StatusEngine.Process.HYKE_SALESFORCE,
    )


process_factory.register_new_process(
    StatusEngine.Process.BK_TRAINING_CALL_SCHEDULED, process_bk_training_call_scheduled)


def process_bk_training_call_cancelled(item):
    if item.processstate != StatusEngine.ProcessState.PENDING:
        return

    try:
        progress_status = ProgressStatus.objects.get(email__iexact=item.email)
        progress_status.bookkeepingsetupstatus = ProgressStatus.Status.RESCHEDULE
        progress_status.save()
    except ProgressStatus.DoesNotExist:
        logger.exception(
            f"Can't find a progress status for email = {item.email}")
        return

    StatusEngine.objects.create(
        email=item.email,
        processstate=item.processstate,
        outcome=item.outcome,
        process=StatusEngine.Process.FOLLOWUP_BK_TRAINING,
        formationtype=StatusEngine.FormationType.HYKE_DAILY,
        executed=timezone.now() + relativedelta(days=2),
    )

    StatusEngine.objects.create(
        email=item.email,
        processstate=item.processstate,
        outcome=item.outcome,
        process=item.process,
        formationtype=StatusEngine.Process.HYKE_SALESFORCE,
    )


process_factory.register_new_process(
    StatusEngine.Process.BK_TRAINING_CALL_CANCELLED, process_bk_training_call_cancelled)


def scheduled_system():
    print("Scheduled task is started for Hyke System...")

    items = StatusEngine.objects.filter(Q(outcome=StatusEngine.Status.SCHEDULED) & Q(
        formationtype=StatusEngine.FormationType.HYKE_SYSTEM))

    print("Active items in the job: " + str(len(items)))

    db.close_old_connections()

    for item in items:
        process_factory.process_run(item.process, item)

    print(
        f"Scheduled task is completed for {StatusEngine.FormationType.HYKE_SYSTEM}...\n")


if __name__ == "__main__":
    scheduled_system()
