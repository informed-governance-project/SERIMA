(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var reportField        = document.getElementById("id_report");
        var questionField      = document.getElementById("id_question_options");
        var answerField        = document.getElementById("id_predefined_answer");
        var nextQuestionField  = document.getElementById("id_next_question_options");

        if (!reportField || !questionField || !answerField || !nextQuestionField) {
            return;
        }

        var marker = "/conditionalquestionoption/";
        var idx = window.location.pathname.indexOf(marker);
        if (idx === -1) { return; }
        var basePath = window.location.pathname.substring(0, idx + marker.length);

        var initialAnswer       = answerField.value;
        var initialNextQuestion = nextQuestionField.value;
        var initialQuestion     = questionField.value;

        // ── Helpers ──────────────────────────────────────────────────────

        function clearOptions(select) {
            select.innerHTML = "";
        }

        function addEmptyOption(select) {
            var opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "---------";
            select.appendChild(opt);
        }

        function populateSelect(select, items, selectedId) {
            clearOptions(select);
            addEmptyOption(select);
            items.forEach(function (item) {
                var opt = document.createElement("option");
                opt.value = item.id;
                opt.textContent = item.label;
                if (selectedId && String(item.id) === String(selectedId)) {
                    opt.selected = true;
                }
                select.appendChild(opt);
            });
        }

        function populateGroupedSelect(select, items, selectedId) {
            clearOptions(select);
            addEmptyOption(select);

            var groups = {};
            var order  = [];
            items.forEach(function (item) {
                if (!groups[item.category]) {
                    groups[item.category] = [];
                    order.push(item.category);
                }
                groups[item.category].push(item);
            });

            order.forEach(function (cat) {
                var optgroup = document.createElement("optgroup");
                optgroup.label = cat;
                groups[cat].forEach(function (item) {
                    var opt = document.createElement("option");
                    opt.value = item.id;
                    opt.textContent = item.label;
                    if (selectedId && String(item.id) === String(selectedId)) {
                        opt.selected = true;
                    }
                    optgroup.appendChild(opt);
                });
                select.appendChild(optgroup);
            });
        }

        // ── Level 1: report → question_options ───────────────────────────

        function refreshQuestions(selectedQuestion) {
            var reportId = reportField.value;
            if (!reportId) {
                refreshDependentOptions(null, null);
                return;
            }

            fetch(basePath + "report-questions/" + reportId + "/", {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    populateGroupedSelect(questionField, data.questions || [], selectedQuestion);
                    if (questionField.value) {
                        refreshDependentOptions(initialAnswer, initialNextQuestion);
                        initialAnswer       = null;
                        initialNextQuestion = null;
                    } else {
                        refreshDependentOptions(null, null);
                    }
                });
        }

        // ── Level 2: question_options → answers + next_question_options ──

        function refreshDependentOptions(selectedAnswer, selectedNextQuestion) {
            var reportId          = reportField.value;
            var questionOptionsId = questionField.value;

            // no report → clear everything downstream
            if (!reportId) {
                clearOptions(questionField);
                addEmptyOption(questionField);
                populateSelect(answerField, [], null);
                populateSelect(nextQuestionField, [], null);
                return;
            }

            // no question → clear only answers and next question
            if (!questionOptionsId) {
                populateSelect(answerField, [], null);
                populateSelect(nextQuestionField, [], null);
                return;
            }

            fetch(basePath + "dependent-options/" + questionOptionsId + "/", {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    populateSelect(answerField,       data.answers       || [], selectedAnswer);
                    populateSelect(nextQuestionField, data.next_questions || [], selectedNextQuestion);
                });
        }

        // ── Event listeners ──────────────────────────────────────────────

        reportField.addEventListener("change", function () {
            refreshQuestions(null);
        });

        questionField.addEventListener("change", function () {
            refreshDependentOptions(null, null);
        });

        // ── Initial load ─────────────────────────────────────────────────

        if (reportField.value) {
            refreshQuestions(initialQuestion);
        } else {
            refreshDependentOptions(initialAnswer, initialNextQuestion);
        }
    });
})();
