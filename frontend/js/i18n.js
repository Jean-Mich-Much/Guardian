(function () {
    "use strict";

    let translations = {};
    let currentLanguage = "fr";

    function getNestedValue(object, key) {
        return key.split(".").reduce((value, part) => (
            value && Object.prototype.hasOwnProperty.call(value, part)
                ? value[part]
                : undefined
        ), object);
    }

    async function loadLanguage(language) {
        if (!translations[language]) {
            throw new Error(`La langue ${language} n'est pas intégrée à Guardian.`);
        }
    }

    async function getSavedLanguage() {
        return window.pywebview.api.get_language();
    }

    async function saveLanguage(language) {
        await window.pywebview.api.set_language(language);
    }

    function translate(key, variables) {
        let value = getNestedValue(translations[currentLanguage], key);
        if (value === undefined) {
            value = getNestedValue(translations.fr, key);
        }
        if (value === undefined) {
            return key;
        }
        if (variables) {
            Object.keys(variables).forEach((name) => {
                value = value.replaceAll(`{${name}}`, String(variables[name]));
            });
        }
        return value;
    }

    function applyTranslations(root) {
        const scope = root || document;
        scope.querySelectorAll("[data-i18n]").forEach((element) => {
            element.textContent = translate(element.dataset.i18n);
        });
        scope.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
            element.placeholder = translate(element.dataset.i18nPlaceholder);
        });
        scope.querySelectorAll("[data-i18n-title]").forEach((element) => {
            element.title = translate(element.dataset.i18nTitle);
        });
    }

    async function setLanguage(language) {
        if (!["fr", "en"].includes(language)) {
            language = "fr";
        }
        if (!translations[language]) {
            await loadLanguage(language);
        }
        currentLanguage = language;
        await saveLanguage(language);
        document.documentElement.lang = language;
        applyTranslations(document);
        window.dispatchEvent(new CustomEvent("guardian-language-change", {
            detail: { language },
        }));
    }

    async function initialize() {
        translations = await window.pywebview.api.get_translations();
        await Promise.all([loadLanguage("fr"), loadLanguage("en")]);
        const saved = await getSavedLanguage();
        const systemLanguage = (navigator.language || "fr").toLowerCase().startsWith("fr")
            ? "fr"
            : "en";
        await setLanguage(saved || systemLanguage);
    }

    window.guardianI18n = {
        initialize,
        setLanguage,
        translate,
        applyTranslations,
        getCurrentLanguage: () => currentLanguage,
    };
})();