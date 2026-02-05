// Pandas.js - JavaScript для работы с Pandas анализом

class PandasAnalyzer {
    constructor() {
        this.state = {
            isAnalyzing: false,
            currentFile: null,
            analysisHistory: [],
            lastResult: null
        };

        // Элементы DOM
        this.elements = {
            uploadForm: null,
            monthInput: null,
            fileInput: null,
            analysisResults: null,
            analysisHistory: null,
            analysisModal: null,
            analysisProgress: null,
            analysisMessage: null,
            detailsText: null,
            analysisDetails: null
        };

        // Настройки
        this.settings = {
            maxFileSize: 50 * 1024 * 1024, // 50MB
            allowedExtensions: ['.xlsx', '.xls', '.csv'],
            autoLoadHistory: true,
            showProgressDetails: true
        };

        this.initialized = false;
    }

    async init() {
        if (this.initialized) return;

        try {
            this.cacheElements();
            this.setupEventListeners();
            this.setupHotkeys();

            if (this.settings.autoLoadHistory) {
                await this.loadAnalysisHistory();
            }

            this.initialized = true;
            console.log('PandasAnalyzer initialized successfully');
        } catch (error) {
            console.error('Failed to initialize PandasAnalyzer:', error);
            NotificationManager.error('Ошибка инициализации анализатора');
        }
    }

    cacheElements() {
        this.elements = {
            uploadForm: document.getElementById('uploadForm'),
            monthInput: document.getElementById('monthInput'),
            fileInput: document.getElementById('fileInput'),
            analysisResults: document.getElementById('analysisResults'),
            analysisHistory: document.getElementById('analysisHistory'),
            analysisModal: document.getElementById('analysisModal'),
            analysisProgress: document.getElementById('analysisProgress'),
            analysisMessage: document.getElementById('analysisMessage'),
            detailsText: document.getElementById('detailsText'),
            analysisDetails: document.getElementById('analysisDetails'),
            importFile: document.getElementById('importFile'),
            importProgress: document.getElementById('importProgress')
        };

        this.analysisModal = this.elements.analysisModal ?
            new bootstrap.Modal(this.elements.analysisModal) : null;
    }

    setupEventListeners() {
        // Форма загрузки
        if (this.elements.uploadForm) {
            this.elements.uploadForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.startAnalysis();
            });
        }

        // Поле выбора файла
        if (this.elements.fileInput) {
            this.elements.fileInput.addEventListener('change', (e) => {
                this.handleFileSelection(e.target.files[0]);
            });
        }

        // Drag and drop
        this.setupDragAndDrop();
    }

    setupDragAndDrop() {
        const dropArea = document.querySelector('.card-body');
        if (!dropArea) return;

        // Предотвращаем поведение по умолчанию
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // Подсветка области при перетаскивании
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            dropArea.classList.add('highlight');
        }

        function unhighlight() {
            dropArea.classList.remove('highlight');
        }

        // Обработка drop
        dropArea.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;

            if (files.length > 0) {
                const file = files[0];
                this.handleFileSelection(file);

                // Устанавливаем файл в input
                if (this.elements.fileInput) {
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(file);
                    this.elements.fileInput.files = dataTransfer.files;
                }
            }
        }, false);
    }

    setupHotkeys() {
        if (!window.hotkeyManager) return;

        const hotkeys = [
            {
                key: 'ctrl+o',
                action: () => {
                    if (this.elements.fileInput) {
                        this.elements.fileInput.click();
                    }
                },
                description: 'Открыть файл'
            },
            {
                key: 'ctrl+enter',
                action: () => {
                    if (this.elements.uploadForm) {
                        this.elements.uploadForm.dispatchEvent(new Event('submit'));
                    }
                },
                description: 'Запустить анализ'
            },
            {
                key: 'f1',
                action: () => {
                    this.showHelp();
                },
                description: 'Показать справку'
            }
        ];

        hotkeys.forEach(hotkey => {
            window.hotkeyManager.register(hotkey.key, hotkey.action, {
                description: hotkey.description
            });
        });
    }

    handleFileSelection(file) {
        if (!file) return;

        // Проверка размера файла
        if (file.size > this.settings.maxFileSize) {
            NotificationManager.error(
                `Файл слишком большой. Максимальный размер: ${this.formatFileSize(this.settings.maxFileSize)}`
            );
            this.resetFileInput();
            return;
        }

        // Проверка расширения файла
        const fileExt = '.' + file.name.split('.').pop().toLowerCase();
        if (!this.settings.allowedExtensions.includes(fileExt)) {
            NotificationManager.error(
                `Неподдерживаемый формат файла. Допустимые форматы: ${this.settings.allowedExtensions.join(', ')}`
            );
            this.resetFileInput();
            return;
        }

        this.state.currentFile = file;

        // Показываем информацию о файле
        this.showFileInfo(file);

        NotificationManager.success(`Файл "${file.name}" выбран для анализа`);
    }

    showFileInfo(file) {
        const fileInfoElement = document.getElementById('fileInfo');
        if (!fileInfoElement) return;

        const fileSize = this.formatFileSize(file.size);
        const fileType = this.getFileType(file.name);

        fileInfoElement.innerHTML = `
            <div class="alert alert-info">
                <div class="d-flex align-items-center">
                    <i class="fas fa-file-excel fa-2x me-3 text-success"></i>
                    <div>
                        <h6 class="mb-1">${file.name}</h6>
                        <p class="mb-0">
                            <small>Размер: ${fileSize} | Тип: ${fileType} | Дата: ${new Date(file.lastModified).toLocaleDateString()}</small>
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    async startAnalysis() {
        if (this.state.isAnalyzing) return;

        const month = this.elements.monthInput ? this.elements.monthInput.value : '';
        const file = this.state.currentFile;

        // Валидация
        if (!month) {
            NotificationManager.error('Выберите месяц для анализа');
            this.elements.monthInput?.focus();
            return;
        }

        if (!file) {
            NotificationManager.error('Выберите файл для анализа');
            this.elements.fileInput?.focus();
            return;
        }

        // Начинаем анализ
        this.state.isAnalyzing = true;
        this.showAnalysisModal();

        try {
            const result = await this.performAnalysis(month, file);
            await this.handleAnalysisResult(result, month, file.name);

        } catch (error) {
            this.handleAnalysisError(error);
        } finally {
            this.state.isAnalyzing = false;
            this.hideAnalysisModal();
        }
    }

    showAnalysisModal() {
        if (!this.analysisModal) return;

        this.updateProgress(0, 'Подготовка к анализу...');
        this.analysisModal.show();
    }

    hideAnalysisModal() {
        if (!this.analysisModal) return;

        // Сбрасываем прогресс
        this.updateProgress(0, '');

        // Скрываем детали
        if (this.elements.analysisDetails) {
            this.elements.analysisDetails.classList.add('d-none');
        }

        // Закрываем модальное окно с задержкой для анимации
        setTimeout(() => {
            if (this.analysisModal) {
                this.analysisModal.hide();
            }
        }, 500);
    }

    updateProgress(percent, message, details = '') {
        if (this.elements.analysisProgress) {
            this.elements.analysisProgress.style.width = `${percent}%`;
        }

        if (this.elements.analysisMessage) {
            this.elements.analysisMessage.textContent = message;
        }

        if (this.elements.detailsText && details) {
            this.elements.detailsText.textContent = details;
            if (this.elements.analysisDetails) {
                this.elements.analysisDetails.classList.remove('d-none');
            }
        }
    }

    async performAnalysis(month, file) {
        const formData = new FormData();
        formData.append('month', month);
        formData.append('file', file);

        // Симуляция прогресса
        const steps = [
            { percent: 10, message: 'Загрузка файла на сервер...', details: 'Шаг 1 из 8' },
            { percent: 20, message: 'Чтение данных Excel...', details: 'Шаг 2 из 8' },
            { percent: 30, message: 'Проверка структуры данных...', details: 'Шаг 3 из 8' },
            { percent: 40, message: 'Парсинг дат и времени...', details: 'Шаг 4 из 8' },
            { percent: 50, message: 'Фильтрация по выбранному месяцу...', details: 'Шаг 5 из 8' },
            { percent: 60, message: 'Группировка данных по филиалам...', details: 'Шаг 6 из 8' },
            { percent: 70, message: 'Расчет сумм и агрегация...', details: 'Шаг 7 из 8' },
            { percent: 80, message: 'Формирование отчета...', details: 'Шаг 8 из 8' },
            { percent: 90, message: 'Сохранение результатов...', details: 'Завершение' }
        ];

        // Обновляем прогресс
        steps.forEach((step, index) => {
            setTimeout(() => {
                this.updateProgress(step.percent, step.message, step.details);
            }, index * 500);
        });

        // Отправляем запрос на сервер
        const response = await fetch('/api/pandas/analyze', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Ошибка сервера: ${response.status} - ${errorText}`);
        }

        // Финальный прогресс
        this.updateProgress(100, 'Анализ завершен! Скачивание файла...');

        return await response.blob();
    }

    async handleAnalysisResult(blob, month, filename) {
        // Сохраняем результат
        this.state.lastResult = {
            blob: blob,
            month: month,
            filename: filename,
            timestamp: new Date()
        };

        // Скачиваем файл
        const monthNames = this.getMonthNames();
        const resultFilename = `анализ_${monthNames[month - 1]}_${new Date().toISOString().split('T')[0]}.xlsx`;

        FileManager.downloadBlob(blob, resultFilename);

        // Показываем результаты
        this.showAnalysisResults(month, filename, resultFilename);

        // Обновляем историю
        await this.addToHistory(month, filename, resultFilename);

        // Сбрасываем форму
        this.resetForm();

        NotificationManager.success('Анализ успешно завершен! Файл скачан.');
    }

    handleAnalysisError(error) {
        console.error('Analysis error:', error);

        let errorMessage = 'Произошла ошибка при анализе';

        if (error.message.includes('не найден')) {
            errorMessage = 'В файле не найдены необходимые колонки данных';
        } else if (error.message.includes('формат')) {
            errorMessage = 'Неверный формат файла или данных';
        } else if (error.message.includes('месяц')) {
            errorMessage = 'Нет данных за выбранный месяц';
        }

        NotificationManager.error(`${errorMessage}: ${error.message}`);

        // Показываем детали ошибки
        if (this.elements.analysisResults) {
            this.elements.analysisResults.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-triangle me-2"></i>Ошибка анализа</h5>
                    <p><strong>${errorMessage}</strong></p>
                    <p class="mb-0"><small>Детали: ${error.message}</small></p>
                </div>

                <div class="text-center mt-4">
                    <button class="btn btn-outline-primary" onclick="window.pandasAnalyzer.startAnalysis()">
                        <i class="fas fa-redo me-2"></i>Попробовать снова
                    </button>
                </div>
            `;
        }
    }

    showAnalysisResults(month, originalFilename, resultFilename) {
        if (!this.elements.analysisResults) return;

        const monthNames = this.getMonthNames();
        const fileSize = this.state.lastResult ?
            this.formatFileSize(this.state.lastResult.blob.size) : 'N/A';

        this.elements.analysisResults.innerHTML = `
            <div class="alert alert-success">
                <h5><i class="fas fa-check-circle me-2"></i>Анализ успешно завершен!</h5>
                <p>Файл <strong>${originalFilename}</strong> проанализирован за <strong>${monthNames[month - 1]}</strong> месяц.</p>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-body">
                            <h6><i class="fas fa-info-circle me-2"></i>Детали анализа</h6>
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>Исходный файл:</strong></td>
                                    <td>${originalFilename}</td>
                                </tr>
                                <tr>
                                    <td><strong>Месяц анализа:</strong></td>
                                    <td>${monthNames[month - 1]}</td>
                                </tr>
                                <tr>
                                    <td><strong>Результат:</strong></td>
                                    <td>${resultFilename}</td>
                                </tr>
                                <tr>
                                    <td><strong>Размер:</strong></td>
                                    <td>${fileSize}</td>
                                </tr>
                                <tr>
                                    <td><strong>Дата выполнения:</strong></td>
                                    <td>${new Date().toLocaleString('ru-RU')}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-body">
                            <h6><i class="fas fa-download me-2"></i>Действия</h6>
                            <div class="d-grid gap-2">
                                <button class="btn btn-success" onclick="window.pandasAnalyzer.downloadResult()">
                                    <i class="fas fa-file-excel me-2"></i>Скачать результат
                                </button>
                                <button class="btn btn-outline-primary" onclick="window.pandasAnalyzer.startAnalysis()">
                                    <i class="fas fa-redo me-2"></i>Новый анализ
                                </button>
                                <button class="btn btn-outline-info" onclick="window.pandasAnalyzer.showResultPreview()">
                                    <i class="fas fa-eye me-2"></i>Предпросмотр
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-body">
                    <h6><i class="fas fa-chart-bar me-2"></i>Что содержит результат:</h6>
                    <ul>
                        <li>Сводную таблицу по филиалам</li>
                        <li>Сумму количества по каждому филиалу</li>
                        <li>Сумму стоимости (с НДС) по каждому филиалу</li>
                        <li>Общий итог по всем филиалам</li>
                        <li>Отформатированные числовые значения</li>
                    </ul>
                </div>
            </div>
        `;
    }

    async loadAnalysisHistory() {
        try {
            // В реальном приложении здесь был бы запрос к API
            // Сейчас используем mock данные
            await this.mockLoadHistory();

            if (this.elements.analysisHistory) {
                this.renderAnalysisHistory();
            }

        } catch (error) {
            console.error('Error loading analysis history:', error);
        }
    }

    async mockLoadHistory() {
        // Mock данные для истории
        this.state.analysisHistory = [
            {
                id: 1,
                month: 11,
                originalFilename: 'data_export_november.xlsx',
                resultFilename: 'analysis_november_2023.xlsx',
                timestamp: new Date('2023-11-30T14:30:00'),
                fileSize: 24576,
                status: 'success'
            },
            {
                id: 2,
                month: 10,
                originalFilename: 'october_report.xlsx',
                resultFilename: 'analysis_october_2023.xlsx',
                timestamp: new Date('2023-10-31T10:15:00'),
                fileSize: 32768,
                status: 'success'
            },
            {
                id: 3,
                month: 9,
                originalFilename: 'september_data.xls',
                resultFilename: 'analysis_september_2023.xlsx',
                timestamp: new Date('2023-09-30T16:45:00'),
                fileSize: 18432,
                status: 'success'
            }
        ];

        // Имитация задержки сети
        return new Promise(resolve => setTimeout(resolve, 300));
    }

    renderAnalysisHistory() {
        if (!this.elements.analysisHistory) return;

        const history = this.state.analysisHistory;

        if (history.length === 0) {
            this.elements.analysisHistory.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-history fa-2x mb-3"></i>
                    <p>История анализов пуста</p>
                </div>
            `;
            return;
        }

        let html = '<div class="list-group">';

        history.forEach(item => {
            const monthNames = this.getMonthNames();
            const fileSize = this.formatFileSize(item.fileSize);
            const timeAgo = this.formatTimeAgo(item.timestamp);

            html += `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between align-items-start">
                        <div class="flex-grow-1 me-3">
                            <div class="d-flex align-items-center mb-1">
                                <i class="fas fa-file-excel text-success me-2"></i>
                                <h6 class="mb-0">${item.originalFilename}</h6>
                                <span class="badge bg-info ms-2">${monthNames[item.month - 1]}</span>
                            </div>
                            <p class="mb-1 text-muted">
                                <small>
                                    <i class="fas fa-calendar me-1"></i>
                                    ${item.timestamp.toLocaleDateString('ru-RU')}
                                    <i class="fas fa-clock ms-2 me-1"></i>
                                    ${item.timestamp.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                                </small>
                            </p>
                            <p class="mb-0">
                                <small>
                                    <i class="fas fa-hdd me-1"></i>${fileSize}
                                    <span class="ms-2">${timeAgo}</span>
                                </small>
                            </p>
                        </div>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-success"
                                    onclick="window.pandasAnalyzer.downloadHistoryItem(${item.id})"
                                    title="Скачать">
                                <i class="fas fa-download"></i>
                            </button>
                            <button class="btn btn-outline-info"
                                    onclick="window.pandasAnalyzer.viewHistoryItem(${item.id})"
                                    title="Просмотреть">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-outline-danger"
                                    onclick="window.pandasAnalyzer.deleteHistoryItem(${item.id})"
                                    title="Удалить">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        this.elements.analysisHistory.innerHTML = html;
    }

    async addToHistory(month, originalFilename, resultFilename) {
        const historyItem = {
            id: Date.now(),
            month: parseInt(month),
            originalFilename: originalFilename,
            resultFilename: resultFilename,
            timestamp: new Date(),
            fileSize: this.state.lastResult?.blob?.size || 0,
            status: 'success'
        };

        this.state.analysisHistory.unshift(historyItem);

        // Сохраняем в localStorage (в реальном приложении - на сервер)
        this.saveHistoryToStorage();

        // Обновляем отображение
        this.renderAnalysisHistory();
    }

    saveHistoryToStorage() {
        try {
            const historyToSave = this.state.analysisHistory.map(item => ({
                ...item,
                timestamp: item.timestamp.toISOString()
            }));

            localStorage.setItem('pandasAnalysisHistory', JSON.stringify(historyToSave));
        } catch (error) {
            console.error('Error saving history to storage:', error);
        }
    }

    loadHistoryFromStorage() {
        try {
            const savedHistory = localStorage.getItem('pandasAnalysisHistory');
            if (savedHistory) {
                const parsedHistory = JSON.parse(savedHistory);
                this.state.analysisHistory = parsedHistory.map(item => ({
                    ...item,
                    timestamp: new Date(item.timestamp)
                }));
            }
        } catch (error) {
            console.error('Error loading history from storage:', error);
        }
    }

    downloadResult() {
        if (!this.state.lastResult?.blob) {
            NotificationManager.error('Нет данных для скачивания');
            return;
        }

        const monthNames = this.getMonthNames();
        const month = this.state.lastResult.month;
        const filename = `анализ_${monthNames[month - 1]}_${new Date().toISOString().split('T')[0]}.xlsx`;

        FileManager.downloadBlob(this.state.lastResult.blob, filename);
        NotificationManager.success('Файл скачан');
    }

    async showResultPreview() {
        if (!this.state.lastResult?.blob) {
            NotificationManager.error('Нет данных для предпросмотра');
            return;
        }

        try {
            // Читаем Excel файл (упрощенная версия)
            const text = await this.readExcelAsText(this.state.lastResult.blob);
            this.displayPreview(text);

        } catch (error) {
            console.error('Error reading Excel file:', error);
            NotificationManager.error('Не удалось прочитать файл для предпросмотра');
        }
    }

    async readExcelAsText(blob) {
        // В реальном приложении здесь была бы библиотека для чтения Excel
        // Сейчас возвращаем mock данные

        return new Promise(resolve => {
            setTimeout(() => {
                const mockData = `
Филиал\tСумма по полю Кількість\tСумма по полю Стоимость СНДС
Киев\t125\t187500.00
Харьков\t89\t133500.00
Одесса\t67\t100500.00
Днепр\t45\t67500.00
Львов\t34\t51000.00
Общий итог\t360\t540000.00
                `.trim();
                resolve(mockData);
            }, 500);
        });
    }

    displayPreview(text) {
        const previewModal = document.getElementById('previewModal');
        if (!previewModal) return;

        const previewContent = document.getElementById('previewContent');
        if (previewContent) {
            // Преобразуем tab-разделенный текст в таблицу HTML
            const rows = text.split('\n');
            let html = '<div class="table-responsive"><table class="table table-bordered">';

            rows.forEach((row, rowIndex) => {
                const cells = row.split('\t');
                html += '<tr>';

                cells.forEach((cell, cellIndex) => {
                    if (rowIndex === 0) {
                        html += `<th class="table-primary">${cell}</th>`;
                    } else {
                        const cellClass = rowIndex === rows.length - 1 ? 'table-success fw-bold' : '';
                        html += `<td class="${cellClass}">${cell}</td>`;
                    }
                });

                html += '</tr>';
            });

            html += '</table></div>';

            previewContent.innerHTML = `
                <h5>Предпросмотр результатов анализа</h5>
                <p class="text-muted">${new Date().toLocaleString('ru-RU')}</p>
                ${html}
                <div class="mt-3">
                    <button class="btn btn-success" onclick="window.pandasAnalyzer.downloadResult()">
                        <i class="fas fa-download me-2"></i>Скачать полный файл
                    </button>
                </div>
            `;
        }

        const modal = new bootstrap.Modal(previewModal);
        modal.show();
    }

    downloadHistoryItem(id) {
        const item = this.state.analysisHistory.find(i => i.id === id);
        if (!item) {
            NotificationManager.error('Элемент истории не найден');
            return;
        }

        // В реальном приложении здесь был бы запрос к API для скачивания файла
        NotificationManager.info('Функция скачивания из истории будет реализована в следующей версии');
    }

    viewHistoryItem(id) {
        const item = this.state.analysisHistory.find(i => i.id === id);
        if (!item) {
            NotificationManager.error('Элемент истории не найден');
            return;
        }

        // Показываем информацию об элементе
        const monthNames = this.getMonthNames();

        const modalContent = `
            <div class="modal-header">
                <h5 class="modal-title">Детали анализа</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <table class="table">
                    <tr>
                        <td><strong>Исходный файл:</strong></td>
                        <td>${item.originalFilename}</td>
                    </tr>
                    <tr>
                        <td><strong>Месяц:</strong></td>
                        <td>${monthNames[item.month - 1]}</td>
                    </tr>
                    <tr>
                        <td><strong>Результат:</strong></td>
                        <td>${item.resultFilename}</td>
                    </tr>
                    <tr>
                        <td><strong>Дата выполнения:</strong></td>
                        <td>${item.timestamp.toLocaleString('ru-RU')}</td>
                    </tr>
                    <tr>
                        <td><strong>Размер файла:</strong></td>
                        <td>${this.formatFileSize(item.fileSize)}</td>
                    </tr>
                    <tr>
                        <td><strong>Статус:</strong></td>
                        <td>
                            <span class="badge bg-success">
                                <i class="fas fa-check me-1"></i>Успешно
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
                <button type="button" class="btn btn-primary" onclick="window.pandasAnalyzer.downloadHistoryItem(${item.id})">
                    <i class="fas fa-download me-2"></i>Скачать
                </button>
            </div>
        `;

        this.showCustomModal(modalContent);
    }

    deleteHistoryItem(id) {
        confirmAction(
            'Удаление из истории',
            'Вы уверены, что хотите удалить этот элемент из истории?',
            () => {
                this.state.analysisHistory = this.state.analysisHistory.filter(i => i.id !== id);
                this.saveHistoryToStorage();
                this.renderAnalysisHistory();
                NotificationManager.success('Элемент удален из истории');
            }
        );
    }

    resetForm() {
        if (this.elements.uploadForm) {
            this.elements.uploadForm.reset();
        }

        this.state.currentFile = null;

        // Очищаем информацию о файле
        const fileInfoElement = document.getElementById('fileInfo');
        if (fileInfoElement) {
            fileInfoElement.innerHTML = '';
        }

        // Сбрасываем input файла
        this.resetFileInput();
    }

    resetFileInput() {
        if (this.elements.fileInput) {
            this.elements.fileInput.value = '';
        }
    }

    showCustomModal(content) {
        // Создаем динамическое модальное окно
        const modalId = 'customModal-' + Date.now();
        const modalHtml = `
            <div class="modal fade" id="${modalId}" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        ${content}
                    </div>
                </div>
            </div>
        `;

        // Добавляем в DOM
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Показываем модальное окно
        const modalElement = document.getElementById(modalId);
        const modal = new bootstrap.Modal(modalElement);

        modal.show();

        // Удаляем модальное окно после закрытия
        modalElement.addEventListener('hidden.bs.modal', () => {
            modalElement.remove();
        });
    }

    showHelp() {
        const helpContent = `
            <div class="modal-header">
                <h5 class="modal-title"><i class="fas fa-question-circle me-2"></i>Справка по Pandas анализу</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <h6>Как работает анализ:</h6>
                <ol>
                    <li>Загрузите Excel файл с данными</li>
                    <li>Выберите месяц для анализа</li>
                    <li>Нажмите "Запустить анализ"</li>
                    <li>Система обработает данные и создаст отчет</li>
                    <li>Скачайте результат в формате Excel</li>
                </ol>

                <h6>Требования к файлу:</h6>
                <ul>
                    <li>Формат: .xlsx или .xls</li>
                    <li>Обязательные колонки:
                        <ul>
                            <li><code>Родитель</code> - название филиала</li>
                            <li><code>Дата статуса</code> - дата в формате ДД.ММ.ГГГГ ЧЧ:ММ:СС</li>
                            <li><code>Количество</code> - числовое значение</li>
                            <li><code>Стоимость (с НДС)</code> - числовое значение</li>
                        </ul>
                    </li>
                    <li>Данные начинаются с 8 строки</li>
                    <li>Последние 2 строки игнорируются</li>
                </ul>

                <h6>Результат анализа:</h6>
                <p>Создается Excel файл с таблицей, содержащей:</p>
                <ul>
                    <li>Список филиалов</li>
                    <li>Сумму количества по каждому филиалу</li>
                    <li>Сумму стоимости по каждому филиалу</li>
                    <li>Общий итог</li>
                </ul>

                <div class="alert alert-info mt-3">
                    <i class="fas fa-lightbulb me-2"></i>
                    <strong>Совет:</strong> Используйте горячие клавиши для быстрого доступа к функциям
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Понятно</button>
            </div>
        `;

        this.showCustomModal(helpContent);
    }

    // Вспомогательные методы
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Б';

        const k = 1024;
        const sizes = ['Б', 'КБ', 'МБ', 'ГБ'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    getFileType(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const types = {
            'xlsx': 'Excel (новый формат)',
            'xls': 'Excel (старый формат)',
            'csv': 'CSV файл',
            'pdf': 'PDF документ',
            'txt': 'Текстовый файл'
        };

        return types[ext] || 'Неизвестный формат';
    }

    getMonthNames() {
        return [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ];
    }

    formatTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) {
            return 'только что';
        } else if (diffMins < 60) {
            return `${diffMins} мин. назад`;
        } else if (diffHours < 24) {
            return `${diffHours} ч. назад`;
        } else if (diffDays < 30) {
            return `${diffDays} дн. назад`;
        } else {
            return 'более месяца назад';
        }
    }
}

// Функции для глобального использования
function initPandasAnalyzer() {
    window.pandasAnalyzer = new PandasAnalyzer();
    window.pandasAnalyzer.init();

    return window.pandasAnalyzer;
}

function confirmAction(title, message, callback) {
    const confirmModal = document.getElementById('confirmModal');
    if (!confirmModal) return;

    document.getElementById('confirmModalTitle').textContent = title;
    document.getElementById('confirmModalBody').textContent = message;

    const modal = new bootstrap.Modal(confirmModal);
    const button = document.getElementById('confirmModalButton');

    const newButton = button.cloneNode(true);
    button.parentNode.replaceChild(newButton, button);

    newButton.onclick = function() {
        modal.hide();
        if (callback) callback();
    };

    modal.show();
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, находимся ли мы на странице Pandas анализа
    if (window.location.pathname.includes('/page/pandas') ||
        document.querySelector('[data-module="pandas"]')) {
        initPandasAnalyzer();
    }
});

// Экспорт для глобального использования
window.PandasAnalyzer = PandasAnalyzer;
window.initPandasAnalyzer = initPandasAnalyzer;
