import logging
import os
from collections import OrderedDict

from django.conf import settings
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from governanceplatform.utils.weasyprint_fetcher import RestrictedURLFetcher

from .globals import REGIONAL_AREA
from .models import Answer, Incident, IncidentWorkflow

# Increasing weasyprint log level
for logger_name in ["weasyprint", "fontTools", "fontTools.subset"]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)


def get_pdf_report(incident: Incident, incident_workflow: IncidentWorkflow, request: HttpRequest):
    # TO DO : improve for more than 2 level ?
    sectors: dict[str, list[str]] = {}
    # boolean to see if it's report or incident
    report_name = None
    report_timeline = None
    incident.incident_starting_date = None
    incident.incident_resolution_date = None

    for sector in incident.affected_sectors.all():
        sector_name = sector.get_safe_translation()

        if sector.parent:
            parent_name = sector.parent.get_safe_translation()
            sectors.setdefault(parent_name, []).append(sector_name)
        else:
            if sector_name not in sectors:
                sectors[sector_name] = []

    incident_workflows_answer: dict[str, dict[str, str, list[str]]] = {}
    incident_workflows_impact: dict[str, list[str]] = {}
    incident_workflows_answer_sorted = {}
    # display for the full incident or just a report
    if incident_workflow is None:
        report_list = incident.get_latest_incident_workflows()
        lastest_report = incident.get_latest_incident_workflow()
        if lastest_report:
            report_timeline = lastest_report.report_timeline
    else:
        report_list = [incident_workflow]
        report_name = incident_workflow.workflow.name
        report_timeline = incident_workflow.report_timeline

    if report_timeline:
        incident.incident_detection_date = report_timeline.incident_detection_date
        incident.incident_starting_date = report_timeline.incident_starting_date
        incident.incident_resolution_date = report_timeline.incident_resolution_date

    for incident_workflow in report_list:
        workflow_name = incident_workflow.workflow
        incident_workflows_answer.setdefault(workflow_name, {})
        incident_workflows_impact.setdefault(workflow_name, [])

        answers = Answer.objects.filter(incident_workflow=incident_workflow).order_by("question_options__position")
        for answer in answers:
            populate_questions_answers(
                answer,
                incident_workflows_answer[workflow_name],
            )

        for workflow_name, category_dict in incident_workflows_answer.items():
            sorted_category_dict = OrderedDict()

            sorted_categories = sorted(category_dict.items(), key=lambda item: item[0].position)

            for category_obj, question_dict in sorted_categories:
                sorted_question_dict = OrderedDict(sorted(question_dict.items(), key=lambda item: item[0].position))
                sorted_category_dict[category_obj] = sorted_question_dict

            incident_workflows_answer_sorted[workflow_name] = sorted_category_dict

        # impacts
        incident_workflows_impact[workflow_name].extend(incident_workflow.impacts.all().order_by("translations__label").distinct())
        incident_workflows_impact[workflow_name] = list(
            {impact.id: impact.label for impact in incident_workflows_impact[workflow_name]}.values()
        )

    # Render the HTML file

    static_theme_dir = settings.STATIC_THEME_DIR
    font_config = FontConfiguration()

    output_from_parsed_template = render_to_string(
        "report/incidents/template.html",
        {
            "incident": incident,
            "incident_workflows_answer": incident_workflows_answer_sorted,
            "incident_workflows_impact": incident_workflows_impact,
            "sectors": sectors,
            "report_name": report_name,
            "report_list": report_list,
        },
        request=request,
    )

    htmldoc = HTML(
        string=output_from_parsed_template,
        base_url=static_theme_dir,
        url_fetcher=RestrictedURLFetcher(),
    )

    stylesheets = [
        CSS(os.path.join(static_theme_dir, "css/custom.css"), font_config=font_config),
        CSS(os.path.join(static_theme_dir, "css/report.css"), font_config=font_config),
    ]

    return htmldoc.write_pdf(stylesheets=stylesheets, pdf_variant="pdf/ua-1", font_config=font_config)


def populate_questions_answers(answer: Answer, preliminary_questions_answers: dict):
    incident_workflow_timestamp = answer.incident_workflow.timestamp
    question_option = answer.question_options

    if answer.incident_workflow.timestamp < answer.question_options.updated_at and answer.question_options.historic.all():
        old_question_option = answer.question_options.historic.filter(timestamp__gte=incident_workflow_timestamp).first()
        question_option = old_question_option

    category_label = question_option.category_option
    question_label = question_option
    question_dict = preliminary_questions_answers.setdefault(category_label, {})
    answer_list = question_dict.setdefault(question_label, [])

    if answer.predefined_answers.all():
        answer_list.extend(answer.predefined_answers.all())
        if question_option.question.question_type in ["MT", "ST"]:
            answer_list.append(f"{_('Details')}:\r\n{answer}")
    else:
        answer_string = answer
        if question_option.question.question_type == "RL":
            REGIONAL_AREA_DICT = dict(REGIONAL_AREA)
            region_name_list = [REGIONAL_AREA_DICT.get(region_code, region_code) for region_code in filter(None, str(answer).split(","))]
            answer_string = " - ".join(map(str, region_name_list))
        if question_option.question.question_type == "CL":
            COUNTRY_DICT = dict(countries)
            region_name_list = [COUNTRY_DICT.get(region_code, region_code) for region_code in filter(None, str(answer).split(","))]
            answer_string = " - ".join(map(str, region_name_list))
        answer_list.append(answer_string)
