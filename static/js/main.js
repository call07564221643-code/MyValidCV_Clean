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
});

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
    const q = question.toLowerCase();

    if (q.includes('discount') || q.includes('offer') || q.includes('coupon')) {
        return 'When MyValidCV has an active discount, it will be shown on the Plans page or shared by support. I can explain the plan value, but I cannot promise an unannounced discount. If a code is available, use it before checkout.';
    }

    if (q.includes('refund') || q.includes('cancel') || q.includes('terms') || q.includes('privacy') || q.includes('condition')) {
        return 'Payments are processed securely through the checkout provider. Refunds and cancellations depend on the plan terms, usage, and timing. Please review the Terms, Privacy, and Use of Data links in the footer, and contact support@myvalidcv.com for account-specific refund help.';
    }

    if (q.includes('payment') || q.includes('pay') || q.includes('stripe') || q.includes('card') || q.includes('receipt')) {
        return 'Choose a plan, click Pay Now, and complete secure checkout. After payment, MyValidCV shows a confirmation/receipt page and updates your plan. Card details are handled by the payment provider, not stored directly by MyValidCV.';
    }

    if (q.includes('report') || q.includes('score') || q.includes('ats') || q.includes('result')) {
        return 'ATS v2 explains your CV-to-role evidence match across skills, requirements, evidence and readability. The Truth Gate distinguishes verified evidence, keyword-only mentions and claims needing confirmation or proof. It improves your documents; it does not predict hiring success.';
    }

    if (q.includes('enterprise') || q.includes('bulk') || q.includes('team') || q.includes('hire')) {
        return 'Enterprise is for teams that need bulk CV comparison against a role. It helps rank candidates, show match percentages, and identify missing evidence. It is useful for recruitment screening, but final hiring decisions should still include human review.';
    }

    if (q.includes('plan') || q.includes('price') || q.includes('plus') || q.includes('free')) {
        return 'Free includes 5 analyses. Plus includes 20 analyses and generated CV and cover-letter drafts. Enterprise supports up to 50 advisory bulk CV comparisons with human review. Check the Plans page for the current price.';
    }

    if (q.includes('how') || q.includes('work') || q.includes('start') || q.includes('upload') || q.includes('validate')) {
        return 'The simple journey is: upload your CV, paste a job advert or URL, click Validate, then review the report. MyValidCV shows matched evidence, missing requirements, recruiter risks, and a recommended CV/cover-letter direction.';
    }

    if (q.includes('cv') || q.includes('cover') || q.includes('rewrite') || q.includes('draft')) {
        return 'MyValidCV helps you improve the CV for a specific job. Green wording is safe rewording from your CV, yellow is stronger presentation of existing evidence, and red means the claim is not evidenced enough yet. The cover letter should summarise your strongest matched evidence.';
    }

    return 'MyValidCV promises a fast, simple way to know whether your CV is ready for a specific job: upload CV, add job advert, validate, improve, apply. Ask me about reports, plans, payments, refunds, discounts, or how to get started.';
}

// ============================================================================
// EXPORT FOR EXTERNAL USE
// ============================================================================

window.FormHandler = FormHandler;
window.Utils = Utils;
