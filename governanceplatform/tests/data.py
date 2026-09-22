# data for tests
# companies
companies_data = [
    {
        "identifier": "COM1",
        "name": "Test Company 1",
        "country": "FR",
        "address": "123 Rue de Paris",
        "email": "contact1@testcompany.com",
        "phone_number": "+33123456789",
        "categories": ["Critical"],
    },
    {
        "identifier": "COM2",
        "name": "Test Company 2",
        "country": "BE",
        "address": "56 Boulevard de Bruxelles",
        "email": "contact2@testcompany.com",
        "phone_number": "+32212345678",
        "categories": ["Public"],
    },
]

functionalities_data = [
    {"name": "Reporting", "type": "reporting"},
    {"name": "so", "type": "securityobjectives"},
]

regulators_data = [
    {
        "id": 1,
        "name": "REG1",
        "full_name": "Regulator1",
        "description": "Regulator responsible for NIS",
        "country": "LU",
        "address": "123 rue de Luxembourg",
        "email_for_notification": "regulator1@reg.lu",
        "functionalities": [{"type": "securityobjectives"}],
    },
    {
        "id": 2,
        "name": "REG2",
        "full_name": "Regulator2",
        "description": "Regulator responsible for NIS2",
        "country": "LU",
        "address": "123 rue de Luxembourg",
        "email_for_notification": "regulator2@reg2.lu",
        "functionalities": [],
    },
]

observers_data = [
    {
        "id": 1,
        "name": "CERT1",
        "full_name": "CERT1",
        "country": "LU",
        "address": "123 rue de Luxembourg",
        "email_for_notification": "cert1@cert1.lu",
        "is_receiving_all_incident": True,
    }
]

permission_groups = [
    {
        "name": "PlatformAdmin",
    },
    {
        "name": "RegulatorAdmin",
    },
    {
        "name": "RegulatorUser",
    },
    {
        "name": "ObserverAdmin",
    },
    {
        "name": "ObserverUser",
    },
    {
        "name": "OperatorAdmin",
    },
    {
        "name": "OperatorUser",
    },
    {
        "name": "IncidentUser",
    },
]

sectors = [
    {"acronym": "ENE", "name": "Energy"},
    {"acronym": "TRA", "name": "Transport"},
    {"acronym": "HEA", "name": "Health"},
    {
        "acronym": "GAS",
        "name": "Gas",
        "parent": {"acronym": "ENE", "translations__name": "Energy"},
    },
    {
        "acronym": "ELEC",
        "name": "Electricity",
        "parent": {"acronym": "ENE", "translations__name": "Energy"},
    },
    {
        "acronym": "ROAD",
        "name": "Road transport",
        "parent": {"acronym": "TRA", "translations__name": "Transport"},
    },
    {
        "acronym": "BOAT",
        "name": "Boat transport",
        "parent": {"acronym": "TRA", "translations__name": "Transport"},
    },
]

regulations = [
    {"id": 1, "label": "NIS", "regulators": [{"translations__name": "REG1"}]},
    {"id": 2, "label": "GDPR", "regulators": [{"translations__name": "REG2"}]},
]

users = [
    # Regulator
    {
        "email": "regadmin@reg1.lu",
        "first_name": "regadmin@reg1.lu",
        "last_name": "regadmin@reg1.lu",
        "password": "secret",
        "is_staff": True,
        "accepted_terms": True,
        "is_superuser": False,
        "regulators": [{"id": 1}],
        "groups": [{"name": "RegulatorAdmin"}],
    },
    {
        "email": "regadmin@reg2.lu",
        "first_name": "regadmin@reg2.lu",
        "last_name": "regadmin@reg2.lu",
        "password": "secret",
        "is_staff": True,
        "accepted_terms": True,
        "is_superuser": False,
        "regulators": [{"id": 2}],
        "groups": [{"name": "RegulatorAdmin"}],
    },
    {
        "email": "reguser@reg2.lu",
        "first_name": "reguser@reg2.lu",
        "last_name": "reguser@reg2.lu",
        "password": "secret",
        "is_staff": True,
        "accepted_terms": True,
        "is_superuser": False,
        "regulators": [{"id": 2}],
        "groups": [{"name": "RegulatorUser"}],
    },
    {
        "email": "reguser@reg1.lu",
        "first_name": "reguser@reg1.lu",
        "last_name": "reguser@reg1.lu",
        "password": "secret",
        "is_staff": True,
        "accepted_terms": True,
        "is_superuser": False,
        "regulators": [{"id": 1}],
        "groups": [{"name": "RegulatorUser"}],
    },
    # Operator
    {
        "email": "opadmin@com1.lu",
        "first_name": "opadmin@com1.lu",
        "last_name": "opadmin@com1.lu",
        "password": "secret",
        "is_staff": True,
        "accepted_terms": True,
        "is_superuser": False,
        "companies": [{"identifier": "COM1"}],
        "groups": [{"name": "OperatorAdmin"}],
    },
    {
        "email": "opuser@com1.lu",
        "first_name": "opuser@com1.lu",
        "last_name": "opuser@com1.lu",
        "password": "secret",
        "is_staff": False,
        "accepted_terms": True,
        "is_superuser": False,
        "companies": [{"identifier": "COM1"}],
        "groups": [{"name": "OperatorUser"}],
    },
    {
        "email": "opadmin@com2.lu",
        "first_name": "opadmin@com2.lu",
        "last_name": "opadmin@com2.lu",
        "password": "secret",
        "is_staff": True,
        "accepted_terms": True,
        "is_superuser": False,
        "companies": [{"identifier": "COM2"}],
        "groups": [{"name": "OperatorAdmin"}],
    },
    {
        "email": "opuser@com2.lu",
        "first_name": "opuser@com2.lu",
        "last_name": "opuser@com2.lu",
        "password": "secret",
        "is_staff": False,
        "accepted_terms": True,
        "is_superuser": False,
        "companies": [{"identifier": "COM2"}],
        "groups": [{"name": "OperatorUser"}],
    },
    # Observer
    {
        "email": "obsadm@cert1.lu",
        "first_name": "obsadm@cert1.lu",
        "last_name": "obsadm@cert1.lu",
        "password": "secret",
        "is_staff": True,
        "accepted_terms": True,
        "is_superuser": False,
        "observers": [{"id": 1}],
        "groups": [{"name": "ObserverAdmin"}],
    },
    # Incident User
    {
        "email": "iu1@iu.lu",
        "first_name": "iu1@iu.lu",
        "last_name": "iu1@iu.lu",
        "password": "secret",
        "is_staff": False,
        "accepted_terms": True,
        "is_superuser": False,
        "groups": [{"name": "IncidentUser"}],
    },
    {
        "email": "iu2@iu.lu",
        "first_name": "iu2@iu.lu",
        "last_name": "iu2@iu.lu",
        "password": "secret",
        "is_staff": False,
        "accepted_terms": True,
        "is_superuser": False,
        "groups": [{"name": "IncidentUser"}],
    },
    # PlatformAdmin
    {
        "email": "pa@pa.lu",
        "first_name": "pa@pa.lu",
        "last_name": "pa@pa.lu",
        "password": "secret",
        "is_staff": True,
        "accepted_terms": True,
        "is_superuser": False,
        "groups": [{"name": "PlatformAdmin"}],
    },
]
