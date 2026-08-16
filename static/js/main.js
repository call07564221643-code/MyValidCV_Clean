/**
 * MyValidCV - Main JavaScript
 * Theme toggle and loading states
 */

// ============================================================================
// THEME TOGGLE
// ============================================================================

class ThemeManager {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.init();
    }

    init() {
        this.applyTheme(this.theme);
        this.setupToggle();
    }

    applyTheme(theme) {
        // Store preference
        localStorage.setItem('theme', theme);
        this.theme = theme;

        // Apply theme to document
        if (theme === 'dark') {
            document.documentElement.setAttribute('data-bs-theme', 'dark');
            document.body.classList.add('bg-dark');
        } else {
            document.documentElement.setAttribute('data-bs-theme', 'light');
            document.body.classList.remove('bg-dark');
        }
        this.updateToggleIcon();
    }

    toggle() {
        const newTheme = this.theme === 'light' ? 'dark' : 'light';
        this.applyTheme(newTheme);
    }

    setupToggle() {
        // Look for theme toggle button
        const toggleBtn = document.getElementById('themeToggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggle());
            this.updateToggleIcon();
        }
    }

    updateToggleIcon() {
        const icon = document.getElementById('themeToggleIcon');
        if (icon) {
            icon.textContent = this.theme === 'light' ? '☾' : '☀';
        }
        const toggleBtn = document.getElementById('themeToggle');
        if (toggleBtn) {
            const label = this.theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode';
            toggleBtn.setAttribute('aria-label', label);
            toggleBtn.setAttribute('title', label);
        }
    }
}

// ============================================================================
// FORM HANDLING
// ============================================================================

class FormHandler {
    static setLoading(button, isLoading = true) {
        const text = button.querySelector('[id*="Text"]');
        const spinner = button.querySelector('.spinner-border');

        if (isLoading) {
            button.disabled = true;
            button.classList.add('loading');
            if (text) text.style.opacity = '0.7';
            if (spinner) spinner.classList.remove('d-none');
        } else {
            button.disabled = false;
            button.classList.remove('loading');
            if (text) text.style.opacity = '1';
            if (spinner) spinner.classList.add('d-none');
        }
    }

    static clearErrors(form) {
        const errors = form.querySelectorAll('.invalid-feedback');
        errors.forEach(error => error.style.display = 'none');
    }

    static showError(form, message) {
        const errorDiv = form.querySelector('[id*="Error"]') ||
                         document.createElement('div');
        if (!errorDiv.id) {
            errorDiv.id = 'formError';
            errorDiv.className = 'alert alert-danger mt-3';
            errorDiv.role = 'alert';
            form.appendChild(errorDiv);
        }
        errorDiv.innerHTML = `<span>${message}</span>`;
        errorDiv.style.display = 'block';
    }
}

// ============================================================================
// UTILITIES
// ============================================================================

class Utils {
    /**
     * Format file size for display
     */
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    /**
     * Validate email format
     */
    static isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    /**
     * Get CSRF token from cookie
     */
    static getCsrfToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Show toast notification
     */
    static showToast(message, type = 'info', duration = 3000) {
        const toastHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999; width: 300px;">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        const toastDiv = document.createElement('div');
        toastDiv.innerHTML = toastHTML;
        document.body.appendChild(toastDiv.firstElementChild);

        if (duration > 0) {
            setTimeout(() => {
                document.querySelector('.alert').remove();
            }, duration);
        }
    }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme manager
    window.themeManager = new ThemeManager();

    // Setup dynamic form validation
    setupFormValidation();

    // Add smooth page transitions
    setupPageTransitions();

    // Setup customer-service assistant
    setupSiteAssistant();

    // Setup reusable copy buttons
    setupCopyActions();

    // Setup reusable experience ratings
    setupFeedbackRatings();

    // Save Stage 2 bullet decisions without reloading the report
    setupBulletReviews();
});

function setupBulletReviews() {
    const progress = document.querySelector('[data-bullet-progress]');
    const applyForm = document.querySelector('[data-bullet-apply-form]');
    const applyButton = applyForm?.querySelector('button[type="submit"]');
    const updateProgress = (summary) => {
        if (progress && summary) {
            progress.textContent = `${summary.total} suggestions · ${summary.pending} pending · ${summary.approved} approved · ${summary.applied} applied`;
        }
        if (applyButton && summary) {
            applyButton.disabled = summary.ready === 0;
            applyButton.textContent = summary.ready
                ? `Apply ${summary.ready} reviewed change${summary.ready === 1 ? '' : 's'} to CV draft`
                : (summary.applied ? 'CV draft is up to date' : 'Choose bullets before applying');
        }
    };

    document.querySelectorAll('[data-bullet-decision-form]').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const card = form.closest('[data-bullet-card]');
            const button = form.querySelector('button[type="submit"]');
            const originalLabel = button?.textContent || '';
            if (button) {
                button.disabled = true;
                button.textContent = 'Saving…';
            }
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                    body: new FormData(form)
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'The decision could not be saved.');

                const state = card?.querySelector('[data-bullet-state]');
                if (state) {
                    state.className = `bullet-state ${data.status}`;
                    state.textContent = data.status_label;
                }
                const proposed = card?.querySelector('[data-bullet-proposed]');
                if (proposed && data.display_text) proposed.textContent = data.display_text;
                const applicationState = card?.querySelector('[data-bullet-application-state]');
                if (applicationState) {
                    applicationState.className = `bullet-application-state ${data.application_is_current ? 'applied' : (data.needs_application ? 'ready' : '')}`;
                    applicationState.textContent = data.application_is_current
                        ? 'Applied to CV'
                        : (data.needs_application ? 'Update ready' : 'Not applied');
                }
                updateProgress(data.summary);
                const editor = form.closest('details');
                if (editor) editor.open = false;
                Utils.showToast(data.message, 'success', 1800);
            } catch (error) {
                Utils.showToast(error.message || 'The decision could not be saved.', 'danger', 3000);
            } finally {
                if (button) {
                    button.disabled = false;
                    button.textContent = originalLabel;
                }
            }
        });
    });

    if (applyForm) {
        applyForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const button = applyForm.querySelector('button[type="submit"]');
            const status = applyForm.querySelector('[data-bullet-apply-status]');
            const originalLabel = button?.textContent || '';
            if (button) {
                button.disabled = true;
                button.textContent = 'Applying…';
            }
            try {
                const response = await fetch(applyForm.action, {
                    method: 'POST',
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                    body: new FormData(applyForm)
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'The approved bullets could not be applied.');

                const editor = document.getElementById('cvDraftEditor');
                if (editor && typeof data.content === 'string') editor.value = data.content;
                (data.applied_ids || []).forEach((suggestionId) => {
                    const card = document.querySelector(`[data-bullet-card][data-suggestion-id="${suggestionId}"]`);
                    const applicationState = card?.querySelector('[data-bullet-application-state]');
                    if (applicationState) {
                        const isCurrent = (data.current_applied_ids || []).includes(suggestionId);
                        applicationState.className = `bullet-application-state${isCurrent ? ' applied' : ''}`;
                        applicationState.textContent = isCurrent ? 'Applied to CV' : 'Not applied';
                    }
                });
                updateProgress(data.summary);
                if (status) {
                    status.classList.remove('report-muted');
                    status.textContent = `${data.message} The CV editor below is now up to date.`;
                }
                document.querySelector('[data-cv-completion-path]')?.classList.toggle(
                    'd-none',
                    !data.summary?.applied
                );
                Utils.showToast(data.message, 'success', 2200);
            } catch (error) {
                if (button) {
                    button.disabled = false;
                    button.textContent = originalLabel;
                }
                if (status) status.textContent = error.message || 'The approved bullets could not be applied.';
                Utils.showToast(error.message || 'The approved bullets could not be applied.', 'danger', 3000);
            }
        });
    }

    const draftForm = document.querySelector('[data-cv-draft-form]');
    if (draftForm) {
        draftForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const button = draftForm.querySelector('button[type="submit"]');
            const status = draftForm.querySelector('[data-cv-save-status]');
            const originalLabel = button?.textContent || '';
            if (button) {
                button.disabled = true;
                button.textContent = 'Saving…';
            }
            try {
                const response = await fetch(draftForm.action, {
                    method: 'POST',
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                    body: new FormData(draftForm)
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'The CV draft could not be saved.');
                if (status) {
                    status.classList.remove('report-muted');
                    status.textContent = 'Saved just now. TXT and DOCX downloads are up to date.';
                }
                Utils.showToast(data.message, 'success', 1800);
            } catch (error) {
                if (status) status.textContent = error.message || 'The CV draft could not be saved.';
                Utils.showToast(error.message || 'The CV draft could not be saved.', 'danger', 3000);
            } finally {
                if (button) {
                    button.disabled = false;
                    button.textContent = originalLabel;
                }
            }
        });
        document.querySelector('[data-save-cv-shortcut]')?.addEventListener('click', () => {
            draftForm.requestSubmit();
        });
    }
}

function setupFeedbackRatings() {
    document.querySelectorAll('[data-feedback-form]').forEach((form) => {
        const widget = form.closest('[data-feedback-widget]');
        const status = form.querySelector('[data-feedback-status]');
        const testimonial = form.querySelector('[data-testimonial-option]');
        const submit = form.querySelector('button[type="submit"]');
        const ratingInputs = form.querySelectorAll('input[name="rating"]');

        const updateTestimonialOption = () => {
            const selected = form.querySelector('input[name="rating"]:checked');
            testimonial.hidden = !selected || Number(selected.value) < 4;
            if (testimonial.hidden) {
                const consent = form.querySelector('input[name="testimonial_consent"]');
                if (consent) consent.checked = false;
            }
        };
        ratingInputs.forEach((input) => input.addEventListener('change', updateTestimonialOption));

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const selected = form.querySelector('input[name="rating"]:checked');
            if (!selected) {
                status.textContent = 'Choose one to five stars.';
                return;
            }
            const categories = Array.from(form.querySelectorAll('input[name="categories"]:checked'))
                .map((input) => input.value);
            const payload = {
                feature: form.dataset.feature,
                context_id: form.dataset.contextId || null,
                rating: Number(selected.value),
                categories,
                comment: form.querySelector('[name="comment"]')?.value || '',
                testimonial_consent: Boolean(form.querySelector('[name="testimonial_consent"]')?.checked),
                public_identity: form.querySelector('[name="public_identity"]:checked')?.value || 'anonymous',
                page_path: window.location.pathname
            };
            submit.disabled = true;
            status.textContent = 'Saving...';
            try {
                const response = await fetch('/feedback/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]')?.value || Utils.getCsrfToken()
                    },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Feedback could not be saved.');
                status.textContent = data.message;
                form.querySelectorAll('input, textarea, select, button').forEach((field) => {
                    field.disabled = true;
                });
                if (widget) {
                    const summaryText = widget.querySelector('summary');
                    if (summaryText) {
                        summaryText.setAttribute('aria-label', `Feedback saved: ${payload.rating} out of 5 stars`);
                    }
                }
            } catch (error) {
                status.textContent = error.message || 'Feedback could not be saved. Please try again.';
                submit.disabled = false;
            }
        });
    });
}

function setupCopyActions() {
    const buttons = document.querySelectorAll('[data-copy-target]');
    buttons.forEach((button) => {
        button.addEventListener('click', async () => {
            const target = document.querySelector(button.dataset.copyTarget);
            if (!target) return;

            const text = target.innerText || target.textContent || '';
            if (!text.trim()) return;

            const originalText = button.textContent;
            try {
                await navigator.clipboard.writeText(text.trim());
                button.textContent = 'Copied';
            } catch (error) {
                const range = document.createRange();
                range.selectNodeContents(target);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                button.textContent = 'Selected';
            }

            window.setTimeout(() => {
                button.textContent = originalText;
            }, 1400);
        });
    });
}

function setupFormValidation() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity() === false) {
                return;
            }
            e.preventDefault();
            e.stopPropagation();

            // Add visual feedback
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                FormHandler.setLoading(submitBtn, true);
                setTimeout(() => {
                    FormHandler.setLoading(submitBtn, false);
                }, 2000);
            }
        });

        // Clear errors on input
        const inputs = form.querySelectorAll('.form-control, .form-check-input');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                FormHandler.clearErrors(form);
            });
        });
    });
}

function setupPageTransitions() {
    // Add fade-in animation to new page loads
    const mainContent = document.querySelector('main');
    if (mainContent) {
        mainContent.classList.add('fade-in');
    }
}

function setupSiteAssistant() {
    const assistant = document.querySelector('[data-assistant]');
    if (!assistant) return;

    const toggle = assistant.querySelector('[data-assistant-toggle]');
    const close = assistant.querySelector('[data-assistant-close]');
    const form = assistant.querySelector('[data-assistant-form]');
    const input = assistant.querySelector('[data-assistant-input]');
    const body = assistant.querySelector('[data-assistant-body]');
    const prompts = assistant.querySelectorAll('[data-assistant-prompt]');
    const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
    const history = [];

    const addMessage = (text, sender = 'bot') => {
        const message = document.createElement('div');
        message.className = `mvcv-assistant-message ${sender}`;
        message.textContent = text;
        body.appendChild(message);
        body.scrollTop = body.scrollHeight;
        history.push({role: sender === 'user' ? 'user' : 'assistant', content: text});
        if (history.length > 8) history.splice(0, history.length - 8);
    };

    const respond = async (question) => {
        addMessage(question, 'user');
        let answer = '';
        const typing = document.createElement('div');
        typing.className = 'mvcv-assistant-message bot';
        typing.textContent = 'Maya is thinking…';
        typing.setAttribute('aria-live', 'polite');
        body.appendChild(typing);
        body.scrollTop = body.scrollHeight;
        input.disabled = true;
        try {
            const response = await fetch('/assistant/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({question, history: history.slice(0, -1)})
            });
            if (response.ok) {
                const data = await response.json();
                answer = data.answer || '';
            }
        } catch (error) {
            answer = '';
        } finally {
            typing.remove();
            input.disabled = false;
            input.focus();
        }
        window.setTimeout(() => addMessage(answer || getAssistantAnswer(question), 'bot'), 180);
    };

    toggle.addEventListener('click', () => {
        const isOpen = assistant.classList.toggle('open');
        toggle.setAttribute('aria-expanded', String(isOpen));
        if (isOpen) input.focus();
    });

    close.addEventListener('click', () => {
        assistant.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
    });

    prompts.forEach((button) => {
        button.addEventListener('click', () => respond(button.dataset.assistantPrompt));
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question) return;
        input.value = '';
        respond(question);
    });
}

function getAssistantAnswer(question) {
    return 'I’m having trouble connecting right now. Please try again in a moment, or ask support@myvalidcv.com if your question is urgent.';
}

// ============================================================================
// EXPORT FOR EXTERNAL USE
// ============================================================================

window.FormHandler = FormHandler;
window.Utils = Utils;
