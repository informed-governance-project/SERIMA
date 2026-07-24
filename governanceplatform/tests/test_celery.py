from celery_worker import app


def test_import_export_extension_tasks_are_registered():
    app.loader.import_default_modules()

    assert "import_export_extensions.tasks.export_data_task" in app.tasks
    assert "import_export_extensions.tasks.import_data_task" in app.tasks
    assert "import_export_extensions.tasks.parse_data_task" in app.tasks
