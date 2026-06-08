document.addEventListener("DOMContentLoaded", function () {
    const fieldsetsSelector = 'fieldset.module, fieldset.module.aligned';
    const inputSelector = 'input:not([type="number"]):not([type="checkbox"]):not([type="hidden"]), textarea';
    const langTabsSelector = '.parler-language-tabs a';
    const saveButtonSelector = 'input[name="_save"]';
    const addAnotherButtonSelector = 'input[name="_addanother"]';
    const continueButtonSelector = 'input[name="_continue"]';
    const currentUrl = window.location.href.split('?')[0];
    const urlId = currentUrl.split("/admin/")[1];
    const langTabs = Array.from(document.querySelectorAll(langTabsSelector))
        .filter(tab => !tab.classList.contains('deletelink'));
    let clear_session_storage = true;

    // remove sessionstorage when leaving page
    window.addEventListener('beforeunload', function () {
        if (localStorage.getItem('parler_tab_switch') === '1') {
            localStorage.removeItem('parler_tab_switch');
            return;
        }

        sessionStorage.clear();
    });

    function saveUrlId() {
        checkUrlId()
        if (urlId) sessionStorage.setItem('urlId', urlId)
    }

    function checkUrlId() {
        const storedUrlId = sessionStorage.getItem('urlId');

        if (urlId && !window.location.href.includes(storedUrlId) && clear_session_storage) {
            sessionStorage.clear();
        }
    }

    function saveCurrentTabData(languageCode) {
        document.querySelectorAll(fieldsetsSelector).forEach(fieldset => {
            fieldset.querySelectorAll(inputSelector).forEach(input => {
                sessionStorage.setItem(`${languageCode}_${input.name}`, input.value);
            });
        });
    }

    function restoreTabData(languageCode) {
        document.querySelectorAll(fieldsetsSelector).forEach(fieldset => {
            fieldset.querySelectorAll(inputSelector).forEach(input => {
                const savedValue = sessionStorage.getItem(`${languageCode}_${input.name}`);
                if (savedValue !== null) input.value = savedValue;
            });
        });
    }

    function removeCurrentTabData(languageCode) {
        document.querySelectorAll(fieldsetsSelector).forEach(fieldset => {
            fieldset.querySelectorAll(inputSelector).forEach(input => {
                sessionStorage.removeItem(`${languageCode}_${input.name}`);
            });
        });
    }

    function getLanguageCodeFromTab(tab) {
        const urlParams = new URLSearchParams(tab.href.split('?')[1]);
        return urlParams.get('language');
    }

    saveUrlId();


    langTabs.forEach(function (tab) {
        tab.addEventListener('click', function (event) {
            event.preventDefault();

            const currentTabElement = document.querySelector('.parler-language-tabs .selected');
            if (!currentTabElement) return;

            saveCurrentTabData(currentTabElement.name);
            restoreTabData(getLanguageCodeFromTab(tab));
            // detect when we changes tab to remove sessionStorage when leaving the page
            localStorage.setItem('parler_tab_switch', '1');
            window.location.href = tab.href;
        });
    });

    const currentTabElement = document.querySelector('.parler-language-tabs .selected');
    if (currentTabElement) restoreTabData(currentTabElement.name);

    const saveButton = document.querySelector(saveButtonSelector);
    const addAnotherButton = document.querySelector(addAnotherButtonSelector);
    const continueButton = document.querySelector(continueButtonSelector);

    if (saveButton) {
        saveButton.addEventListener('click', function () {
            sessionStorage.clear();
        });
    }
    if (addAnotherButton) {
        addAnotherButton.addEventListener('click', function () {
            sessionStorage.clear();
        });
    }
    if (continueButton) {
        continueButton.addEventListener('click', function () {
            clear_session_storage = true;
            const urlParams = new URLSearchParams(window.location.href.split('?')[1]);
            const language_code = urlParams.get('language');
            removeCurrentTabData(language_code)

        });
    }
});
