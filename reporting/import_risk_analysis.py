import json
from collections import Counter, defaultdict
from datetime import datetime

import pytz
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override

from .helpers import generate_combined_uuid
from .models import AssetData, RecommendationData, RiskData, ServiceStat, ThreatData, VulnerabilityData

LANG_VALUES = {1: "fr", 2: "en", 3: "de", 4: "nl"}
TREATMENT_VALUES = {
    1: "REDUC",
    2: "DENIE",
    3: "ACCEP",
    4: "SHARE",
    5: "UNTRE",
}


def validate_json_file(original_filename: str, tmp_path: str) -> None:
    if not original_filename.endswith(".json"):
        raise ValidationError(_("Uploaded file is not a JSON file."))

    with open(tmp_path, "rb") as json_file:
        try:
            json_data = json.load(json_file)
        except json.JSONDecodeError:
            raise ValidationError(_("Uploaded file contains invalid JSON."))

        if not isinstance(json_data, dict):
            raise ValidationError(_("JSON file must contain an object at the root."))

    if "monarc_version" not in json_data:
        raise ValidationError(_("Missing 'monarc_version' key in the JSON file."))

    if "type" not in json_data:
        raise ValidationError(_("Missing 'type' key in the JSON file."))

    if "instance" not in json_data and "instances" not in json_data:
        raise ValidationError(_("JSON file must contain either 'instance' or 'instances'."))


def parsing_risk_data_json(json_file, company_reporting_obj):
    try:
        json_file.seek(0)
        content = json_file.read().decode("utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Error decoding JSON: {str(e)}")

    file_version = tuple(map(int, data["monarc_version"].split(".")))
    refactoring_version = tuple(map(int, "2.13.1".split(".")))
    is_new_version = file_version >= refactoring_version
    language_code = data.get("languageCode", None)
    _translation_cache = {}
    instances = []
    if data["type"] == "instance":
        instance = data["instance"] if is_new_version else _normalize_json(data)
        instances.append(instance)
    elif data["type"] == "anr":
        instances = data["instances"] if is_new_version else data["instances"].values()

    for instance in instances:
        if _is_root_instance(instance, is_new_version):
            normalized_instance = _get_normalized_instance(instance, is_new_version)
            root_service_data = normalized_instance.copy()
            normalized_instance["parent_uuid"] = normalized_instance["uuid"]
            _extract_risks(normalized_instance, root_service_data, company_reporting_obj, is_new_version, language_code, _translation_cache)


def _normalize_json(data):
    normalize_instance = data["instance"].copy()

    for key in ("risks", "children", "amvs", "threats", "vuls", "recos"):
        normalize_instance[key] = data.get(key, {})

    return normalize_instance


def _is_root_instance(instance, is_new_version):
    children = instance.get("children", [])
    if is_new_version:
        is_root = instance.get("level") == 1 and instance.get("position") == 1
    else:
        meta_instance = instance.get("instance", {})
        is_root = meta_instance.get("root") == 0 and meta_instance.get("parent") == 0

    return is_root and bool(children)


def _get_normalized_instance(instance, is_new_version):
    if is_new_version:
        normalized_instance = instance.copy()
        asset_uuid = instance["asset"]["uuid"]
        object_uuid = instance["object"]["uuid"]
        parent_uuid = instance.get("parent_uuid", "")
        normalized_instance["uuid"] = generate_combined_uuid([asset_uuid, object_uuid, parent_uuid])

    else:
        normalized_instance = defaultdict()
        meta_instance = instance["instance"]
        asset_uuid = meta_instance["asset"]
        object_uuid = meta_instance["object"]
        parent_uuid = instance.get("parent_uuid", "")
        risks_data = instance.get("risks", {})
        risks = risks_data if isinstance(risks_data, dict) else {}
        children_data = instance.get("children", {})
        children = children_data if isinstance(children_data, dict) else {}
        instance_risks = risks.values()
        amvs = instance.get("amvs", {})
        threats = instance.get("threats", {})
        vuls = instance.get("vuls", {})
        recos_data = instance.get("recos", {})
        recos = recos_data if isinstance(recos_data, dict) else {}

        for instance_risk in instance_risks:
            txv = instance_risk["threatRate"] * instance_risk["vulnerabilityRate"]
            recommendation_data = recos.get(str(instance_risk["id"]), {})

            instance_risk.update(
                {
                    "informationRisk": amvs.get(str(instance_risk["amv"]), {}),
                    "threat": _get_normalized_threat(instance_risk, threats),
                    "vulnerability": _get_normalized_vulnerability(instance_risk, vuls),
                    "recommendations": recommendation_data.values(),
                    "riskConfidentiality": instance["instance"]["c"] * txv,
                    "riskIntegrity": instance["instance"]["i"] * txv,
                    "riskAvailability": instance["instance"]["d"] * txv,
                }
            )

        normalized_instance.update(
            {
                "uuid": generate_combined_uuid([asset_uuid, object_uuid, parent_uuid]),
                "name": _get_translations_dict(meta_instance, "name"),
                "label": _get_translations_dict(meta_instance, "label"),
                "confidentiality": instance["instance"]["c"],
                "integrity": instance["instance"]["i"],
                "availability": instance["instance"]["d"],
                "instanceRisks": instance_risks,
                "children": children.values(),
            }
        )

    return normalized_instance


def _get_translations_dict(values, field_name):
    translations_dict = {}
    for lang_index in LANG_VALUES.keys():
        key = field_name + str(lang_index)
        name_value = values.get(key, None)
        if name_value:
            translations_dict[key] = name_value
    return translations_dict


def _get_normalized_threat(instance_risk, threats):
    threat_data = threats.get(str(instance_risk["threat"]), {})
    threat_data["confidentiality"] = threat_data.get("c")
    threat_data["integrity"] = threat_data.get("i")
    threat_data["availability"] = threat_data.get("a")
    threat_data["label"] = _get_translations_dict(threat_data, "label")
    threat_data["description"] = _get_translations_dict(threat_data, "description")
    return threat_data


def _get_normalized_vulnerability(instance_risk, vuls):
    vulnerability_data = vuls.get(str(instance_risk["vulnerability"]), {})
    vulnerability_data["label"] = _get_translations_dict(vulnerability_data, "label")
    vulnerability_data["description"] = (_get_translations_dict(vulnerability_data, "description"),)
    return vulnerability_data


def _extract_risks(instance, root_service_data, company_reporting_obj, is_new_version, language_code, cache):
    risks = instance["instanceRisks"]
    children = instance["children"]

    if risks:
        new_service_asset = _create_translations(AssetData, root_service_data, "label", is_new_version, language_code, cache)
        service_stat = ServiceStat.objects.get_or_create(
            service=new_service_asset,
            company_reporting=company_reporting_obj,
        )[0]
        new_asset = _create_translations(AssetData, instance, "label", is_new_version, language_code, cache)

        built = _build_risk_objects(risks, instance, service_stat, new_asset, is_new_version, language_code, cache)
        _save_risks_to_db(built, service_stat)

    # Process child instances recursively
    for child in children:
        normalized_instance = _get_normalized_instance(child, is_new_version)
        normalized_instance["parent_uuid"] = instance["uuid"]
        _extract_risks(normalized_instance, root_service_data, company_reporting_obj, is_new_version, language_code, cache)


def _build_risk_objects(risks, instance, service_stat, new_asset, is_new_version, language_code, cache):
    risks_to_upsert = []
    recommendations_to_upsert = []
    seen_recommendation_uuids = set()
    risk_to_rec_uuids = {}
    risk_uuids = []
    max_risk_values = []
    residual_risk_values = []
    treatment_values = []

    for risk in risks:
        information_risk_uuid = _generate_information_risk_uuid(risk)
        risk["uuid"] = generate_combined_uuid([instance["uuid"], information_risk_uuid])
        risk["risk_treatment"] = TREATMENT_VALUES.get(risk["kindOfMeasure"], "UNSET")
        risk_uuids.append(risk["uuid"])

        new_vulnerability = _create_translations(VulnerabilityData, risk["vulnerability"], "label", is_new_version, language_code, cache)
        new_threat = _create_translations(ThreatData, risk["threat"], "label", is_new_version, language_code, cache)
        risk.update(_calculate_risks(risk))

        if risk["cacheMaxRisk"] != -1 and risk["kindOfMeasure"] != 5:
            max_risk_values.append(risk["cacheMaxRisk"])
        if risk["cacheTargetedRisk"] != -1 and risk["kindOfMeasure"] != 5:
            residual_risk_values.append(risk["cacheTargetedRisk"])
        treatment_values.append(risk["kindOfMeasure"])

        risks_to_upsert.append(
            RiskData(
                uuid=risk["uuid"],
                service=service_stat,
                asset=new_asset,
                threat=new_threat,
                threat_value=risk["threatRate"],
                vulnerability=new_vulnerability,
                vulnerability_value=risk["vulnerabilityRate"],
                residual_risk=risk["cacheTargetedRisk"],
                risk_treatment=risk["risk_treatment"],
                max_risk=risk["cacheMaxRisk"],
                risk_c=risk["riskConfidentiality"],
                risk_i=risk["riskIntegrity"],
                risk_a=risk["riskAvailability"],
                impact_c=instance["confidentiality"],
                impact_i=instance["integrity"],
                impact_a=instance["availability"],
            )
        )

        risk_to_rec_uuids[risk["uuid"]] = []
        for rec in risk["recommendations"]:
            risk_to_rec_uuids[risk["uuid"]].append(rec["uuid"])
            if rec["uuid"] not in seen_recommendation_uuids:
                recommendations_to_upsert.append(
                    RecommendationData(
                        uuid=rec["uuid"],
                        code=rec["code"],
                        description=rec["description"],
                        due_date=_parse_due_date(rec["duedate"]),
                        status=rec["status"],
                    )
                )
                seen_recommendation_uuids.add(rec["uuid"])

    return {
        "risks_to_upsert": risks_to_upsert,
        "recommendations_to_upsert": recommendations_to_upsert,
        "seen_recommendation_uuids": seen_recommendation_uuids,
        "risk_to_rec_uuids": risk_to_rec_uuids,
        "risk_uuids": risk_uuids,
        "max_risk_values": max_risk_values,
        "residual_risk_values": residual_risk_values,
        "treatment_values": treatment_values,
    }


def _save_risks_to_db(built, service_stat):

    RiskData.objects.bulk_create(
        built["risks_to_upsert"],
        update_conflicts=True,
        unique_fields=["uuid", "service"],
        update_fields=[
            "asset",
            "threat",
            "threat_value",
            "vulnerability",
            "vulnerability_value",
            "residual_risk",
            "risk_treatment",
            "max_risk",
            "risk_c",
            "risk_i",
            "risk_a",
            "impact_c",
            "impact_i",
            "impact_a",
        ],
    )

    RecommendationData.objects.bulk_create(
        built["recommendations_to_upsert"],
        update_conflicts=True,
        unique_fields=["uuid"],
        update_fields=["code", "description", "due_date", "status"],
    )

    risk_data_by_uuid = {
        risk_obj.uuid: risk_obj
        for risk_obj in RiskData.objects.filter(
            uuid__in=built["risk_uuids"],
            service=service_stat,
        )
    }

    rec_data_by_uuid = {rec_obj.uuid: rec_obj for rec_obj in RecommendationData.objects.filter(uuid__in=built["seen_recommendation_uuids"])}

    RiskRecommendationM2M = RiskData.recommendations.through

    risk_reco_m2m_to_create = []

    for risk_uuid, rec_uuids in built["risk_to_rec_uuids"].items():
        risk_data_object = risk_data_by_uuid.get(risk_uuid)
        if risk_data_object is None:
            continue
        for rec_uuid in rec_uuids:
            rec_obj = rec_data_by_uuid.get(rec_uuid)
            if rec_obj is None:
                continue

            risk_reco_m2m_to_create.append(
                RiskRecommendationM2M(
                    riskdata_id=risk_data_object.pk,
                    recommendationdata_id=rec_obj.pk,
                )
            )

    RiskRecommendationM2M.objects.bulk_create(risk_reco_m2m_to_create, ignore_conflicts=True)

    treatment_counts = Counter(built["treatment_values"])
    service_stat.avg_current_risks = _update_average(
        service_stat.avg_current_risks,
        service_stat.total_treated_risks,
        built["max_risk_values"],
    )
    service_stat.avg_residual_risks = _update_average(
        service_stat.avg_residual_risks,
        service_stat.total_treated_risks,
        built["residual_risk_values"],
    )
    service_stat.total_risks += len(built["risks_to_upsert"])
    service_stat.total_untreated_risks += treatment_counts.get(5, 0)
    service_stat.total_treated_risks += len(built["risks_to_upsert"]) - treatment_counts.get(5, 0)
    service_stat.total_reduced_risks += treatment_counts.get(1, 0)
    service_stat.total_denied_risks += treatment_counts.get(2, 0)
    service_stat.total_accepted_risks += treatment_counts.get(3, 0)
    service_stat.total_shared_risks += treatment_counts.get(4, 0)
    service_stat.save()


def _create_translations(class_model, values, field_name, is_new_version, language_code, cache):
    uuid = values["uuid"]
    if uuid in cache:
        return cache[uuid]

    new_object, created = class_model.objects.get_or_create(uuid=values["uuid"])

    if created:
        translations = values.get(field_name, None)
        if not translations:
            return new_object

        if is_new_version and language_code:
            with override(language_code):
                new_object.set_current_language(language_code)
                new_object.name = translations
        else:
            for lang_index, lang_code in LANG_VALUES.items():
                name_value = translations.get(field_name + str(lang_index), None)
                if name_value:
                    with override(lang_code):
                        new_object.set_current_language(lang_code)
                        new_object.name = name_value

        new_object.save()

        cache[uuid] = new_object

    return new_object


def _update_average(current_avg, treated_risks, new_risks_values):
    if len(new_risks_values) > 0:
        total_risks = treated_risks + len(new_risks_values)
        weighted_sum = (current_avg * treated_risks) + sum(new_risks_values)
        return weighted_sum / total_risks
    return current_avg


def _generate_information_risk_uuid(risk):
    if risk["informationRisk"]:
        return risk["informationRisk"]["uuid"]
    return risk["threat"]["uuid"] + risk["vulnerability"]["uuid"]


def _calculate_risks(risk):
    def get_risk_value(risk_value, factor):
        risk_value = risk_value if factor else -1
        return max(risk_value, -1)

    threat = risk["threat"]

    return {
        "riskConfidentiality": get_risk_value(risk["riskIntegrity"], threat["confidentiality"]),
        "riskIntegrity": get_risk_value(risk["riskIntegrity"], threat["integrity"]),
        "riskAvailability": get_risk_value(risk["riskAvailability"], threat["availability"]),
    }


def _parse_due_date(duedate):
    if not duedate:
        return None
    if isinstance(duedate, str):
        dt = datetime.fromisoformat(duedate)
        tz = pytz.UTC
    elif isinstance(duedate, dict):
        date_str = duedate.get("date")
        if not date_str:
            return None
        dt = datetime.fromisoformat(date_str)
        tz_name = duedate.get("timezone", "UTC")
        tz = pytz.timezone(tz_name)
    else:
        return None

    if dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt
