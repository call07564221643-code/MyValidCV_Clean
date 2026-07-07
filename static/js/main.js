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
            document.documentElement.removeAttribute('data-bs-theme');
            document.body.classList.remove('bg-dark');
        }
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
            icon.textContent = this.theme === 'light' ? '🌙' : '☀️';
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
});

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

// ============================================================================
// EXPORT FOR EXTERNAL USE
// ============================================================================

window.FormHandler = FormHandler;
window.Utils = Utils;
