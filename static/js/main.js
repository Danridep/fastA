// Общие утилиты для всего приложения

// Уведомления
class NotificationManager {
    static show(message, type = 'info', duration = 5000) {
        const container = document.getElementById('notification-container');
        if (!container) {
            console.error('Notification container not found');
            return;
        }

        const alertClass = {
            'success': 'alert-success',
            'error': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert ${alertClass} alert-dismissible fade show`;
        alertDiv.style.cssText = 'animation: fadeIn 0.3s ease;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        container.appendChild(alertDiv);

        // Автоматическое скрытие
        if (duration > 0) {
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.classList.remove('show');
                    setTimeout(() => alertDiv.remove(), 150);
                }
            }, duration);
        }

        return alertDiv;
    }

    static success(message, duration = 5000) {
        return this.show(message, 'success', duration);
    }

    static error(message, duration = 5000) {
        return this.show(message, 'error', duration);
    }

    static warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }

    static info(message, duration = 5000) {
        return this.show(message, 'info', duration);
    }
}

// Загрузка данных
class DataLoader {
    static async fetchJson(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Accept': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching data:', error);
            NotificationManager.error(`Ошибка загрузки: ${error.message}`);
            throw error;
        }
    }

    static async fetchBlob(url, options = {}) {
        try {
            const response = await fetch(url, options);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.blob();
        } catch (error) {
            console.error('Error fetching blob:', error);
            NotificationManager.error(`Ошибка загрузки файла: ${error.message}`);
            throw error;
        }
    }

    static async postJson(url, data, options = {}) {
        return this.fetchJson(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        });
    }

    static async putJson(url, data, options = {}) {
        return this.fetchJson(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        });
    }

    static async deleteJson(url, options = {}) {
        return this.fetchJson(url, {
            method: 'DELETE',
            ...options
        });
    }
}

// Форматирование
class Formatter {
    static formatDate(dateString, format = 'ru-RU') {
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString(format, {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (error) {
            return dateString;
        }
    }

    static formatNumber(number, decimals = 2) {
        if (number === null || number === undefined) return '0';
        return parseFloat(number).toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    }

    static formatCurrency(amount, currency = '₽') {
        return `${this.formatNumber(amount)} ${currency}`;
    }

    static truncate(text, maxLength = 100) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }
}

// Валидация
class Validator {
    static isEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    static isPhone(phone) {
        const re = /^[\d\s\-\+\(\)]{10,20}$/;
        return re.test(phone);
    }

    static isRequired(value) {
        return value !== null && value !== undefined && value.toString().trim() !== '';
    }

    static isNumber(value) {
        return !isNaN(parseFloat(value)) && isFinite(value);
    }

    static validateForm(formElement) {
        const inputs = formElement.querySelectorAll('[required]');
        let isValid = true;

        inputs.forEach(input => {
            if (!this.isRequired(input.value)) {
                input.classList.add('is-invalid');
                isValid = false;
            } else {
                input.classList.remove('is-invalid');
            }

            // Специальная валидация для email и phone
            if (input.type === 'email' && !this.isEmail(input.value)) {
                input.classList.add('is-invalid');
                isValid = false;
            }

            if (input.type === 'tel' && !this.isPhone(input.value)) {
                input.classList.add('is-invalid');
                isValid = false;
            }
        });

        return isValid;
    }
}

// Работа с файлами
class FileManager {
    static downloadBlob(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    static readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsText(file);
        });
    }

    static readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsDataURL(file);
        });
    }

    static getFileExtension(filename) {
        return filename.split('.').pop().toLowerCase();
    }

    static isImageFile(filename) {
        const ext = this.getFileExtension(filename);
        return ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(ext);
    }

    static isExcelFile(filename) {
        const ext = this.getFileExtension(filename);
        return ['xlsx', 'xls', 'csv'].includes(ext);
    }
}

// Управление состоянием
class StateManager {
    constructor() {
        this.state = {};
        this.listeners = new Map();
    }

    set(key, value) {
        const oldValue = this.state[key];
        this.state[key] = value;

        // Уведомляем слушателей
        if (this.listeners.has(key)) {
            this.listeners.get(key).forEach(callback => callback(value, oldValue));
        }
    }

    get(key, defaultValue = null) {
        return this.state[key] !== undefined ? this.state[key] : defaultValue;
    }

    subscribe(key, callback) {
        if (!this.listeners.has(key)) {
            this.listeners.set(key, new Set());
        }
        this.listeners.get(key).add(callback);

        // Возвращаем функцию отписки
        return () => this.unsubscribe(key, callback);
    }

    unsubscribe(key, callback) {
        if (this.listeners.has(key)) {
            this.listeners.get(key).delete(callback);
        }
    }

    clear(key) {
        delete this.state[key];
        if (this.listeners.has(key)) {
            this.listeners.delete(key);
        }
    }

    clearAll() {
        this.state = {};
        this.listeners.clear();
    }
}

// Горячие клавиши
class HotkeyManager {
    constructor() {
        this.hotkeys = new Map();
        this.enabled = true;

        document.addEventListener('keydown', this.handleKeyDown.bind(this));
    }

    register(combination, callback, options = {}) {
        const hotkey = {
            combination: combination.toLowerCase(),
            callback,
            preventDefault: options.preventDefault !== false,
            stopPropagation: options.stopPropagation || false,
            description: options.description || '',
            enabled: true
        };

        this.hotkeys.set(combination.toLowerCase(), hotkey);

        // Возвращаем функцию отмены регистрации
        return () => this.unregister(combination);
    }

    unregister(combination) {
        this.hotkeys.delete(combination.toLowerCase());
    }

    enable() {
        this.enabled = true;
    }

    disable() {
        this.enabled = false;
    }

    handleKeyDown(event) {
        if (!this.enabled) return;

        // Собираем комбинацию клавиш
        let combination = '';
        if (event.ctrlKey || event.metaKey) combination += 'ctrl+';
        if (event.altKey) combination += 'alt+';
        if (event.shiftKey) combination += 'shift+';
        combination += event.key.toLowerCase();

        // Ищем зарегистрированную комбинацию
        const hotkey = this.hotkeys.get(combination);
        if (hotkey && hotkey.enabled) {
            if (hotkey.preventDefault) {
                event.preventDefault();
            }
            if (hotkey.stopPropagation) {
                event.stopPropagation();
            }
            hotkey.callback(event);
        }
    }

    // Стандартные горячие клавиши
    static registerDefaults() {
        const manager = new HotkeyManager();

        // Ctrl+S - сохранить
        manager.register('ctrl+s', (e) => {
            const saveButton = document.querySelector('[data-action="save"]');
            if (saveButton) saveButton.click();
        }, { description: 'Сохранить' });

        // Ctrl+F - поиск
        manager.register('ctrl+f', (e) => {
            const searchInput = document.querySelector('[data-action="search"]');
            if (searchInput) searchInput.focus();
        }, { description: 'Поиск' });

        // Ctrl+E - экспорт
        manager.register('ctrl+e', (e) => {
            const exportButton = document.querySelector('[data-action="export"]');
            if (exportButton) exportButton.click();
        }, { description: 'Экспорт' });

        // Escape - закрыть/отмена
        manager.register('escape', (e) => {
            const activeModal = document.querySelector('.modal.show');
            if (activeModal) {
                const modalInstance = bootstrap.Modal.getInstance(activeModal);
                if (modalInstance) modalInstance.hide();
            }
        }, { description: 'Закрыть/Отмена' });

        // F5 - обновить
        manager.register('f5', (e) => {
            const refreshButton = document.querySelector('[data-action="refresh"]');
            if (refreshButton) refreshButton.click();
        }, { description: 'Обновить' });

        return manager;
    }
}

// Инициализация приложения
class AppInitializer {
    static init() {
        // Инициализация горячих клавиш
        window.hotkeyManager = HotkeyManager.registerDefaults();

        // Инициализация менеджера состояния
        window.appState = new StateManager();

        // Инициализация Bootstrap компонентов
        this.initBootstrapComponents();

        // Загрузка статистики
        this.loadStats();

        // Настройка сайдбара
        this.setupSidebar();

        console.log('Приложение инициализировано');
    }

    static initBootstrapComponents() {
        // Инициализация тултипов
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        // Инициализация попапов
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }

    static loadStats() {
        // Загружаем статистику для боковой панели
        DataLoader.fetchJson('/api/stats')
            .then(data => {
                const nomenclatureCount = document.getElementById('nomenclature-count');
                const addressesCount = document.getElementById('addresses-count');

                if (nomenclatureCount) {
                    nomenclatureCount.textContent = data.nomenclature || 0;
                }

                if (addressesCount) {
                    addressesCount.textContent = data.addresses || 0;
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки статистики:', error);
            });
    }

    static setupSidebar() {
        const sidebarToggle = document.querySelector('[data-action="toggle-sidebar"]');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                const sidebar = document.getElementById('sidebar');
                const mainContent = document.getElementById('mainContent');
                sidebar.classList.toggle('collapsed');
                mainContent.classList.toggle('expanded');

                // Сохраняем состояние в localStorage
                const isCollapsed = sidebar.classList.contains('collapsed');
                localStorage.setItem('sidebar-collapsed', isCollapsed);
            });
        }

        // Восстанавливаем состояние сайдбара
        const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.getElementById('mainContent');

        if (isCollapsed && sidebar && mainContent) {
            sidebar.classList.add('collapsed');
            mainContent.classList.add('expanded');
        }
    }

    static showLoading() {
        let spinner = document.getElementById('globalLoadingSpinner');
        if (!spinner) {
            spinner = document.createElement('div');
            spinner.id = 'globalLoadingSpinner';
            spinner.className = 'spinner-container';
            spinner.innerHTML = '<div class="spinner"></div>';
            document.body.appendChild(spinner);
        }
    }

    static hideLoading() {
        const spinner = document.getElementById('globalLoadingSpinner');
        if (spinner) {
            spinner.remove();
        }
    }
}

// Утилиты для работы с таблицами
class TableUtils {
    static createDataTable(tableId, options = {}) {
        const table = document.getElementById(tableId);
        if (!table) return null;

        const defaultOptions = {
            paging: true,
            searching: true,
            ordering: true,
            info: true,
            responsive: true,
            language: {
                url: '//cdn.datatables.net/plug-ins/1.11.5/i18n/ru.json'
            },
            dom: '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6"f>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            pageLength: 25,
            lengthMenu: [10, 25, 50, 100]
        };

        return $(table).DataTable({
            ...defaultOptions,
            ...options
        });
    }

    static exportToExcel(tableId, filename = 'table.xlsx') {
        const table = document.getElementById(tableId);
        if (!table) return;

        // Создаем HTML строку таблицы
        let html = '<table>';

        // Заголовки
        html += '<tr>';
        const headers = table.querySelectorAll('thead th');
        headers.forEach(header => {
            html += `<th>${header.textContent}</th>`;
        });
        html += '</tr>';

        // Данные
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            html += '<tr>';
            const cells = row.querySelectorAll('td');
            cells.forEach(cell => {
                html += `<td>${cell.textContent}</td>`;
            });
            html += '</tr>';
        });

        html += '</table>';

        // Создаем и скачиваем файл
        const blob = new Blob([html], { type: 'application/vnd.ms-excel' });
        FileManager.downloadBlob(blob, filename);
    }

    static filterTable(tableId, searchTerm, columnIndex = null) {
        const table = document.getElementById(tableId);
        if (!table) return;

        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            let show = false;
            const cells = row.querySelectorAll('td');

            if (columnIndex !== null) {
                // Поиск в конкретной колонке
                if (columnIndex < cells.length) {
                    const cellText = cells[columnIndex].textContent.toLowerCase();
                    show = cellText.includes(searchTerm.toLowerCase());
                }
            } else {
                // Поиск во всех колонках
                cells.forEach(cell => {
                    if (cell.textContent.toLowerCase().includes(searchTerm.toLowerCase())) {
                        show = true;
                    }
                });
            }

            row.style.display = show ? '' : 'none';
        });
    }
}

// Утилиты для работы с формами
class FormUtils {
    static serializeForm(formId) {
        const form = document.getElementById(formId);
        if (!form) return {};

        const formData = new FormData(form);
        const data = {};

        formData.forEach((value, key) => {
            if (data[key]) {
                if (Array.isArray(data[key])) {
                    data[key].push(value);
                } else {
                    data[key] = [data[key], value];
                }
            } else {
                data[key] = value;
            }
        });

        return data;
    }

    static fillForm(formId, data) {
        const form = document.getElementById(formId);
        if (!form) return;

        Object.keys(data).forEach(key => {
            const element = form.querySelector(`[name="${key}"]`);
            if (element) {
                if (element.type === 'checkbox' || element.type === 'radio') {
                    element.checked = data[key];
                } else {
                    element.value = data[key];
                }
            }
        });
    }

    static clearForm(formId) {
        const form = document.getElementById(formId);
        if (!form) return;

        form.reset();

        // Сбрасываем валидацию
        const invalidElements = form.querySelectorAll('.is-invalid');
        invalidElements.forEach(el => el.classList.remove('is-invalid'));
    }

    static validateAndSubmit(formId, onSubmit) {
        const form = document.getElementById(formId);
        if (!form) return;

        form.addEventListener('submit', function(e) {
            e.preventDefault();

            if (Validator.validateForm(form)) {
                const formData = FormUtils.serializeForm(formId);
                onSubmit(formData);
            } else {
                NotificationManager.warning('Заполните все обязательные поля правильно');
            }
        });
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    AppInitializer.init();

    // Добавляем анимацию появления элементов
    const elements = document.querySelectorAll('.fade-in');
    elements.forEach((el, index) => {
        el.style.animationDelay = `${index * 0.1}s`;
    });

    // Настраиваем подтверждение перед уходом со страницы
    window.addEventListener('beforeunload', function(e) {
        // Можно добавить логику проверки несохраненных изменений
        // if (hasUnsavedChanges) {
        //     e.preventDefault();
        //     e.returnValue = '';
        // }
    });
});

// Экспорт утилит для глобального использования
window.NotificationManager = NotificationManager;
window.DataLoader = DataLoader;
window.Formatter = Formatter;
window.Validator = Validator;
window.FileManager = FileManager;
window.TableUtils = TableUtils;
window.FormUtils = FormUtils;