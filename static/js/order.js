// Order.js - JavaScript для работы с заказами

class OrderManager {
    constructor(sessionId, orderType) {
        this.sessionId = sessionId;
        this.orderType = orderType;
        this.orderData = null;
        this.currentAddress = null;
        this.editData = {};
        this.exportModal = null;
        this.initialized = false;

        // Элементы DOM
        this.elements = {
            addressesList: null,
            tableHeaders: null,
            tableBody: null,
            currentAddressTitle: null,
            itemCount: null,
            quickFillInput: null,
            exportModal: null,
            exportProgress: null,
            loadingContainer: null,
            mainContainer: null
        };

        // Настройки
        this.settings = {
            autoSave: true,
            autoSaveInterval: 30000, // 30 секунд
            validateQuantities: true,
            showEmptyRows: true
        };

        // Состояние
        this.state = {
            hasUnsavedChanges: false,
            isLoading: false,
            isExporting: false,
            lastSaveTime: null
        };

        console.log('OrderManager создан с sessionId:', sessionId, 'orderType:', orderType);
    }

    async init() {
        if (this.initialized) return;

        try {
            console.log('Инициализация OrderManager...');
            this.cacheElements();
            await this.loadOrderData();
            this.setupEventListeners();
            this.setupAutoSave();
            this.setupHotkeys();
            this.initialized = true;

            console.log('OrderManager успешно инициализирован');
        } catch (error) {
            console.error('Ошибка инициализации OrderManager:', error);
            if (window.showError) {
                window.showError('Ошибка инициализации заказа: ' + error.message);
            }
            throw error;
        }
    }

    cacheElements() {
        console.log('Кэширование элементов DOM...');

        this.elements = {
            addressesList: document.getElementById('addressesList'),
            tableHeaders: document.getElementById('tableHeaders'),
            tableBody: document.getElementById('tableBody'),
            currentAddressTitle: document.getElementById('currentAddressTitle'),
            itemCount: document.getElementById('itemCount'),
            quickFillInput: document.getElementById('quickFill'),
            exportModal: document.getElementById('exportModal'),
            exportProgress: document.getElementById('exportProgress'),
            exportProgressBar: document.querySelector('#exportProgress .progress-bar'),
            loadingContainer: document.getElementById('loading-container'),
            mainContainer: document.getElementById('main-container'),
            orderStats: document.getElementById('orderStats')
        };

        console.log('Найденные элементы:', Object.keys(this.elements).filter(key => this.elements[key]));

        if (this.elements.exportModal) {
            this.exportModal = new bootstrap.Modal(this.elements.exportModal);
        }
    }

    async loadOrderData() {
        console.log('Загрузка данных заказа для sessionId:', this.sessionId);

        if (window.showLoading) {
            window.showLoading('Загрузка данных с сервера...');
        }

        this.state.isLoading = true;

        try {
            console.log(`Запрос данных сессии: /api/orders/session/${this.sessionId}`);
            const response = await fetch(`/api/orders/session/${this.sessionId}`);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('HTTP ошибка:', response.status, errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const result = await response.json();
            console.log('Ответ от сервера:', result);

            if (!result.success) {
                throw new Error(result.message || 'Ошибка загрузки данных');
            }

            this.orderData = result.data;

            if (!this.orderData) {
                throw new Error('Нет данных заказа');
            }

            console.log('Данные загружены:', {
                headers: this.orderData.headers?.length || 0,
                addresses: this.orderData.addresses?.length || 0,
                orderType: this.orderData.order_type
            });

            this.renderAddresses();

            if (this.orderData.addresses && this.orderData.addresses.length > 0) {
                this.selectAddress(this.orderData.addresses[0]);
            } else {
                console.warn('Нет адресов в данных заказа');
            }

            this.updateStats();
            this.showMainContent();

            if (window.showNotification) {
                window.showNotification('Данные заказа загружены', 'success');
            }

        } catch (error) {
            console.error('Ошибка загрузки данных заказа:', error);
            throw error;
        } finally {
            this.state.isLoading = false;
        }
    }

    showMainContent() {
        // Скрываем спиннер загрузки
        if (this.elements.loadingContainer) {
            this.elements.loadingContainer.classList.add('d-none');
        }

        // Показываем основной контейнер
        if (this.elements.mainContainer) {
            this.elements.mainContainer.classList.remove('d-none');
            setTimeout(() => {
                this.elements.mainContainer.classList.add('loaded');
            }, 10);
        }
    }

    renderAddresses() {
        if (!this.elements.addressesList || !this.orderData || !this.orderData.addresses) {
            console.warn('Невозможно отобразить адреса: отсутствуют данные');
            return;
        }

        const list = this.elements.addressesList;
        list.innerHTML = '';

        console.log('Отрисовка адресов:', this.orderData.addresses.length);

        this.orderData.addresses.forEach((address, index) => {
            const addressData = this.orderData.addresses_data?.[address] || [];
            const filledCount = addressData.filter(item =>
                item['Кол-во'] && item['Кол-во'].toString().trim() !== ''
            ).length;
            const totalCount = addressData.length;

            const progress = totalCount > 0 ? Math.round((filledCount / totalCount) * 100) : 0;

            const item = document.createElement('div');
            item.className = 'list-group-item list-group-item-action address-item d-flex align-items-center';
            item.dataset.address = address;
            item.dataset.index = index;

            item.innerHTML = `
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <strong class="address-text">${address}</strong>
                        <span class="badge ${filledCount > 0 ? 'bg-success' : 'bg-secondary'}">
                            ${filledCount}/${totalCount}
                        </span>
                    </div>
                    <div class="d-flex align-items-center">
                        <div class="progress flex-grow-1 me-2" style="height: 4px;">
                            <div class="progress-bar ${progress === 100 ? 'bg-success' : 'bg-primary'}"
                                 style="width: ${progress}%"></div>
                        </div>
                        <small class="text-muted">${progress}%</small>
                    </div>
                    <small class="text-muted d-block mt-1">
                        <i class="fas fa-user me-1"></i>
                        ${addressData[0]?.['ФИО получателя'] || 'Нет данных'}
                    </small>
                </div>
                <i class="fas fa-chevron-right ms-2 text-muted"></i>
            `;

            item.addEventListener('click', () => this.selectAddress(address));
            list.appendChild(item);
        });

        // Если нет адресов
        if (this.orderData.addresses.length === 0) {
            list.innerHTML = `
                <div class="text-center p-4 text-muted">
                    <i class="fas fa-map-marked-alt fa-2x mb-3"></i>
                    <p>Нет адресов для отображения</p>
                </div>
            `;
        }
    }

    selectAddress(address) {
        if (this.currentAddress === address) return;

        // Сохраняем изменения предыдущего адреса
        if (this.currentAddress && this.state.hasUnsavedChanges) {
            this.saveAddressChanges(this.currentAddress).catch(console.error);
        }

        this.currentAddress = address;
        console.log('Выбран адрес:', address);

        // Обновляем активный элемент в списке
        document.querySelectorAll('.address-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.address === address) {
                item.classList.add('active');
            }
        });

        // Обновляем заголовок
        if (this.elements.currentAddressTitle) {
            this.elements.currentAddressTitle.innerHTML = `
                <i class="fas fa-edit me-2"></i>Редактирование: <strong class="text-primary">${address}</strong>
            `;
        }

        // Отрисовываем таблицу
        this.renderTable();

        // Прокручиваем к активному элементу
        const activeItem = document.querySelector('.address-item.active');
        if (activeItem) {
            activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    renderTable() {
        if (!this.currentAddress || !this.orderData || !this.elements.tableBody) {
            console.warn('Невозможно отобразить таблицу: отсутствуют данные');
            return;
        }

        const headers = this.orderData.headers || [];
        const data = this.editData[this.currentAddress] ||
                    this.orderData.addresses_data?.[this.currentAddress] || [];

        console.log(`Отрисовка таблицы для адреса "${this.currentAddress}":`, {
            headersCount: headers.length,
            dataCount: data.length
        });

        // Заголовки таблицы
        if (this.elements.tableHeaders) {
            this.elements.tableHeaders.innerHTML = '<th width="50">№</th>';

            headers.forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                th.className = 'align-middle';

                if (header === 'Кол-во') {
                    th.innerHTML = `
                        ${header}
                        <span class="badge bg-info ms-1" title="Заполните количество">
                            <i class="fas fa-pen"></i>
                        </span>
                    `;
                    th.className += ' quantity-header';
                }

                this.elements.tableHeaders.appendChild(th);
            });
        }

        // Тело таблицы
        const tbody = this.elements.tableBody;
        tbody.innerHTML = '';

        if (data.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="${headers.length + 1}" class="text-center p-5 text-muted">
                        <i class="fas fa-database fa-2x mb-3"></i>
                        <p>Нет данных для этого адреса</p>
                    </td>
                </tr>
            `;
            this.updateItemCount(0);
            return;
        }

        // Создаем строки
        data.forEach((row, index) => {
            const tr = document.createElement('tr');
            tr.dataset.index = index;
            tr.innerHTML = `<td class="fw-bold text-center">${index + 1}</td>`;

            headers.forEach(header => {
                const td = document.createElement('td');
                td.className = 'align-middle';

                if (header === 'Кол-во') {
                    td.className += ' quantity-cell';

                    const inputGroup = document.createElement('div');
                    inputGroup.className = 'input-group input-group-sm';

                    const input = document.createElement('input');
                    input.type = 'text';
                    input.className = 'form-control quantity-input text-center';
                    input.value = row[header] || '';
                    input.dataset.index = index;
                    input.dataset.header = header;
                    input.placeholder = '0';

                    if (!input.value) {
                        input.classList.add('is-empty');
                    } else {
                        input.classList.add('is-filled');
                    }

                    // Кнопки для быстрого изменения
                    const buttonGroup = document.createElement('div');
                    buttonGroup.className = 'btn-group btn-group-sm';
                    buttonGroup.innerHTML = `
                        <button type="button" class="btn btn-outline-secondary"
                                data-action="decrement">
                            <i class="fas fa-minus"></i>
                        </button>
                        <button type="button" class="btn btn-outline-secondary"
                                data-action="increment">
                            <i class="fas fa-plus"></i>
                        </button>
                        <button type="button" class="btn btn-outline-danger"
                                data-action="clear">
                            <i class="fas fa-times"></i>
                        </button>
                    `;

                    inputGroup.appendChild(input);
                    inputGroup.appendChild(buttonGroup);
                    td.appendChild(inputGroup);

                    // Обработчики событий
                    input.addEventListener('input', (e) => this.onQuantityInput(e.target));
                    input.addEventListener('focus', (e) => e.target.select());
                    input.addEventListener('blur', (e) => this.validateQuantityInput(e.target));

                    // Обработчики для кнопок
                    buttonGroup.querySelector('[data-action="decrement"]').addEventListener('click', () => {
                        this.adjustQuantity(index, -1);
                    });

                    buttonGroup.querySelector('[data-action="increment"]').addEventListener('click', () => {
                        this.adjustQuantity(index, 1);
                    });

                    buttonGroup.querySelector('[data-action="clear"]').addEventListener('click', () => {
                        this.clearQuantity(index);
                    });

                } else {
                    // Обычные ячейки (только для чтения)
                    td.textContent = row[header] || '';
                    td.title = row[header] || '';

                    // Добавляем иконки для определенных полей
                    if (header === 'Телефон' && row[header]) {
                        td.innerHTML = `
                            <a href="tel:${row[header]}" class="text-decoration-none">
                                <i class="fas fa-phone me-1"></i>${row[header]}
                            </a>
                        `;
                    } else if (header === 'ФИО получателя' && row[header]) {
                        td.innerHTML = `
                            <i class="fas fa-user me-1 text-muted"></i>${row[header]}
                        `;
                    }
                }

                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });

        this.updateItemCount(data.length);
        this.updateAddressCounter();
    }

    onQuantityInput(input) {
        const index = parseInt(input.dataset.index);
        let value = input.value.trim();

        // Сохраняем только цифры
        const numericValue = value.replace(/[^\d]/g, '');
        if (value !== numericValue) {
            input.value = numericValue;
            value = numericValue;
        }

        // Обновляем данные
        if (!this.editData[this.currentAddress]) {
            this.editData[this.currentAddress] = JSON.parse(
                JSON.stringify(this.orderData.addresses_data[this.currentAddress])
            );
        }

        this.editData[this.currentAddress][index]['Кол-во'] = value;

        // Обновляем стиль
        if (value) {
            input.classList.remove('is-empty');
            input.classList.add('is-filled');
        } else {
            input.classList.add('is-empty');
            input.classList.remove('is-filled');
        }

        this.state.hasUnsavedChanges = true;
        this.updateAddressCounter();
    }

    validateQuantityInput(input) {
        const value = input.value.trim();

        if (value && !/^\d+$/.test(value)) {
            input.value = '';
            this.onQuantityInput(input);
            this.showNotification('Введите только цифры для количества', 'warning');
        }
    }

    adjustQuantity(index, delta) {
        const input = document.querySelector(`input[data-index="${index}"][data-header="Кол-во"]`);
        if (!input) return;

        let currentValue = parseInt(input.value) || 0;
        let newValue = currentValue + delta;

        if (newValue < 0) newValue = 0;

        input.value = newValue.toString();
        this.onQuantityInput(input);

        // Анимация изменения
        input.classList.add('changed');
        setTimeout(() => input.classList.remove('changed'), 300);
    }

    clearQuantity(index) {
        const input = document.querySelector(`input[data-index="${index}"][data-header="Кол-во"]`);
        if (!input) return;

        input.value = '';
        this.onQuantityInput(input);

        // Анимация очистки
        input.classList.add('cleared');
        setTimeout(() => input.classList.remove('cleared'), 300);
    }

    updateItemCount(count) {
        if (this.elements.itemCount) {
            this.elements.itemCount.textContent = `${count} позиций`;

            // Добавляем иконку в зависимости от количества
            let icon = 'fa-list';
            if (count > 20) icon = 'fa-th-list';
            if (count > 50) icon = 'fa-table';

            this.elements.itemCount.innerHTML = `
                <i class="fas ${icon} me-1"></i>${count} позиций
            `;
        }
    }

    updateAddressCounter() {
        if (!this.currentAddress) return;

        const addressItems = document.querySelectorAll('.address-item');
        const index = this.orderData.addresses.indexOf(this.currentAddress);

        if (index >= 0 && addressItems[index]) {
            const addressData = this.editData[this.currentAddress] ||
                              this.orderData.addresses_data[this.currentAddress] || [];
            const filledCount = addressData.filter(item =>
                item['Кол-во'] && item['Кол-во'].toString().trim() !== ''
            ).length;
            const totalCount = addressData.length;
            const progress = totalCount > 0 ? Math.round((filledCount / totalCount) * 100) : 0;

            const badge = addressItems[index].querySelector('.badge');
            const progressBar = addressItems[index].querySelector('.progress-bar');

            if (badge) {
                badge.textContent = `${filledCount}/${totalCount}`;
                badge.className = `badge ${filledCount > 0 ? 'bg-success' : 'bg-secondary'}`;
            }

            if (progressBar) {
                progressBar.style.width = `${progress}%`;
                progressBar.className = `progress-bar ${progress === 100 ? 'bg-success' : 'bg-primary'}`;
            }
        }
    }

    updateStats() {
        if (!this.orderData || !this.elements.orderStats) return;

        let totalItems = 0;
        let filledItems = 0;
        let totalQuantity = 0;
        let totalAddresses = this.orderData.addresses?.length || 0;

        this.orderData.addresses?.forEach(address => {
            const addressData = this.editData[address] ||
                              this.orderData.addresses_data?.[address] || [];
            totalItems += addressData.length;

            addressData.forEach(item => {
                const quantity = parseInt(item['Кол-во']) || 0;
                if (quantity > 0) {
                    filledItems++;
                    totalQuantity += quantity;
                }
            });
        });

        const fillPercentage = totalItems > 0 ? Math.round((filledItems / totalItems) * 100) : 0;

        this.elements.orderStats.innerHTML = `
            <div class="row text-center">
                <div class="col-md-3 mb-3">
                    <div class="stat-card p-3 border rounded">
                        <i class="fas fa-map-marker-alt fa-2x text-primary mb-2"></i>
                        <h3 class="mb-1">${totalAddresses}</h3>
                        <small class="text-muted">Адресов</small>
                    </div>
                </div>
                <div class="col-md-3 mb-3">
                    <div class="stat-card p-3 border rounded">
                        <i class="fas fa-boxes fa-2x text-success mb-2"></i>
                        <h3 class="mb-1">${totalItems}</h3>
                        <small class="text-muted">Всего позиций</small>
                    </div>
                </div>
                <div class="col-md-3 mb-3">
                    <div class="stat-card p-3 border rounded">
                        <i class="fas fa-check-circle fa-2x text-warning mb-2"></i>
                        <h3 class="mb-1">${filledItems}</h3>
                        <small class="text-muted">Заполнено</small>
                    </div>
                </div>
                <div class="col-md-3 mb-3">
                    <div class="stat-card p-3 border rounded">
                        <i class="fas fa-percentage fa-2x text-info mb-2"></i>
                        <h3 class="mb-1">${fillPercentage}%</h3>
                        <small class="text-muted">Заполнение</small>
                    </div>
                </div>
            </div>
        `;
    }

    quickFillAll() {
        if (!this.elements.quickFillInput || !this.currentAddress) {
            this.showNotification('Сначала выберите адрес', 'warning');
            return;
        }

        const value = this.elements.quickFillInput.value.trim();
        if (!value || !/^\d+$/.test(value)) {
            this.showNotification('Введите корректное число', 'warning');
            return;
        }

        if (confirm(`Заполнить все поля количеством "${value}" для текущего адреса?`)) {
            const addressData = this.editData[this.currentAddress] ||
                              this.orderData.addresses_data[this.currentAddress] || [];

            addressData.forEach((item, index) => {
                item['Кол-во'] = value;

                // Обновляем input в таблице
                const input = document.querySelector(`input[data-index="${index}"][data-header="Кол-во"]`);
                if (input) {
                    input.value = value;
                    input.classList.remove('is-empty');
                    input.classList.add('is-filled', 'quick-filled');

                    // Анимация
                    setTimeout(() => input.classList.remove('quick-filled'), 500);
                }
            });

            this.updateAddressCounter();
            this.state.hasUnsavedChanges = true;

            this.showNotification(`Все позиции заполнены значением: ${value}`, 'success');
        }
    }

    clearAll() {
        if (!this.currentAddress) {
            this.showNotification('Сначала выберите адрес', 'warning');
            return;
        }

        if (confirm('Вы уверены, что хотите очистить все значения количества для этого адреса?')) {
            const addressData = this.editData[this.currentAddress] ||
                              this.orderData.addresses_data[this.currentAddress] || [];

            addressData.forEach((item, index) => {
                item['Кол-во'] = '';

                // Обновляем input в таблице
                const input = document.querySelector(`input[data-index="${index}"][data-header="Кол-во"]`);
                if (input) {
                    input.value = '';
                    input.classList.add('is-empty');
                    input.classList.remove('is-filled');

                    // Анимация
                    input.classList.add('cleared-all');
                    setTimeout(() => input.classList.remove('cleared-all'), 500);
                }
            });

            this.updateAddressCounter();
            this.state.hasUnsavedChanges = true;

            this.showNotification('Все значения очищены', 'success');
        }
    }

    async saveAddressChanges(address = null) {
        const saveAddress = address || this.currentAddress;
        if (!saveAddress || !this.editData[saveAddress]) return true;

        try {
            const data = {
                address: saveAddress,
                items: this.editData[saveAddress]
            };

            console.log('Сохранение изменений для адреса:', saveAddress);
            const response = await fetch(`/api/orders/session/${this.sessionId}/update`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.message || 'Ошибка сохранения');
            }

            this.state.hasUnsavedChanges = false;
            this.state.lastSaveTime = new Date();

            // Обновляем исходные данные
            this.orderData.addresses_data[saveAddress] = this.editData[saveAddress];

            this.showNotification('Изменения сохранены', 'success');
            this.updateStats();

            return true;
        } catch (error) {
            console.error('Ошибка сохранения:', error);
            this.showNotification(`Ошибка сохранения: ${error.message}`, 'error');
            return false;
        }
    }

    async saveAllChanges() {
        console.log('Сохранение всех изменений...');

        try {
            const promises = [];
            const addresses = Object.keys(this.editData);

            if (addresses.length === 0) {
                this.showNotification('Нет изменений для сохранения', 'info');
                return true;
            }

            for (const address of addresses) {
                const data = {
                    address: address,
                    items: this.editData[address]
                };

                const promise = fetch(`/api/orders/session/${this.sessionId}/update`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                }).then(async response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status} для адреса ${address}`);
                    }
                    return response.json();
                });

                promises.push(promise);
            }

            await Promise.all(promises);

            // Обновляем исходные данные
            Object.keys(this.editData).forEach(address => {
                this.orderData.addresses_data[address] = this.editData[address];
            });

            this.state.hasUnsavedChanges = false;
            this.state.lastSaveTime = new Date();

            this.showNotification('Все изменения сохранены', 'success');
            this.updateStats();

            return true;
        } catch (error) {
            console.error('Ошибка сохранения всех изменений:', error);
            this.showNotification(`Ошибка сохранения: ${error.message}`, 'error');
            return false;
        }
    }

    async exportToExcel() {
        if (this.state.isExporting) {
            this.showNotification('Экспорт уже выполняется', 'warning');
            return;
        }

        try {
            this.state.isExporting = true;

            // Сначала сохраняем изменения
            if (this.state.hasUnsavedChanges) {
                const saved = await this.saveAllChanges();
                if (!saved) {
                    this.state.isExporting = false;
                    return;
                }
            }

            // Показываем модальное окно
            if (this.exportModal) {
                this.exportModal.show();
            }

            // Симуляция прогресса
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 5;
                if (progress <= 90 && this.elements.exportProgressBar) {
                    this.elements.exportProgressBar.style.width = progress + '%';
                }
            }, 100);

            // Отправляем запрос на экспорт
            const response = await fetch(`/api/orders/session/${this.sessionId}/export`, {
                method: 'POST'
            });

            clearInterval(progressInterval);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            // Получаем blob и скачиваем файл
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // Получаем имя файла из заголовков ответа или генерируем
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `заказ_${this.orderData?.order_type || 'unknown'}_${new Date().toISOString().split('T')[0]}.xlsx`;

            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }

            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.state.isExporting = false;

            if (this.exportModal) {
                this.exportModal.hide();
            }

            this.showNotification('Файл успешно экспортирован и скачан', 'success');

        } catch (error) {
            console.error('Ошибка экспорта:', error);
            this.state.isExporting = false;

            if (this.exportModal) {
                this.exportModal.hide();
            }

            this.showNotification(`Ошибка экспорта: ${error.message}`, 'error');
        }
    }

    refreshData() {
        if (confirm('Обновить данные с сервера? Несохраненные изменения будут потеряны.')) {
            this.loadOrderData().then(() => {
                this.editData = {};
                this.state.hasUnsavedChanges = false;
                this.showNotification('Данные обновлены', 'success');
            }).catch(error => {
                this.showNotification(`Ошибка обновления: ${error.message}`, 'error');
            });
        }
    }

    showNotification(message, type = 'info') {
        if (window.showNotification) {
            window.showNotification(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    setupEventListeners() {
        console.log('Настройка обработчиков событий...');

        // Кнопка экспорта
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportToExcel());
        }

        // Кнопка сохранения
        const saveBtn = document.getElementById('saveBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveAllChanges());
        }

        // Кнопка обновления
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshData());
        }

        // Кнопка быстрого заполнения
        const quickFillBtn = document.getElementById('quickFillBtn');
        if (quickFillBtn) {
            quickFillBtn.addEventListener('click', () => this.quickFillAll());
        }

        // Кнопка очистки
        const clearAllBtn = document.getElementById('clearAllBtn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => this.clearAll());
        }

        // Кнопка начала экспорта
        const startExportBtn = document.getElementById('startExportBtn');
        if (startExportBtn) {
            startExportBtn.addEventListener('click', () => this.exportToExcel());
        }

        // Enter в поле быстрого заполнения
        if (this.elements.quickFillInput) {
            this.elements.quickFillInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.quickFillAll();
                }
            });
        }

        // Предотвращение ухода со страницы при несохраненных изменениях
        window.addEventListener('beforeunload', (e) => {
            if (this.state.hasUnsavedChanges) {
                e.preventDefault();
                e.returnValue = 'У вас есть несохраненные изменения. Вы уверены, что хотите уйти?';
                return e.returnValue;
            }
        });
    }

    setupAutoSave() {
        if (!this.settings.autoSave) return;

        setInterval(() => {
            if (this.state.hasUnsavedChanges) {
                this.saveAllChanges().then(success => {
                    if (success) {
                        console.log('Автосохранение выполнено');
                    }
                });
            }
        }, this.settings.autoSaveInterval);
    }

    setupHotkeys() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+S - сохранить
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.saveAllChanges();
            }

            // Ctrl+E - экспорт
            if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
                e.preventDefault();
                this.exportToExcel();
            }

            // F5 - обновить (предотвращаем перезагрузку страницы)
            if (e.key === 'F5') {
                e.preventDefault();
                this.refreshData();
            }

            // Escape - закрыть модальные окна
            if (e.key === 'Escape') {
                const activeModal = document.querySelector('.modal.show');
                if (activeModal) {
                    const modalInstance = bootstrap.Modal.getInstance(activeModal);
                    if (modalInstance) {
                        modalInstance.hide();
                    }
                }
            }

            // Tab - переключение между полями ввода
            if (e.key === 'Tab' && e.target.classList.contains('quantity-input')) {
                e.preventDefault();
                const inputs = Array.from(document.querySelectorAll('.quantity-input'));
                const currentIndex = inputs.indexOf(e.target);
                const direction = e.shiftKey ? -1 : 1;
                const nextIndex = (currentIndex + direction + inputs.length) % inputs.length;

                inputs[nextIndex].focus();
                inputs[nextIndex].select();
            }
        });
    }
}

// Функции для глобального использования
function initOrder(sessionId, orderType) {
    console.log('Инициализация заказа:', { sessionId, orderType });

    try {
        window.orderManager = new OrderManager(sessionId, orderType);
        window.orderManager.init().catch(error => {
            console.error('Ошибка при инициализации OrderManager:', error);
            if (window.showError) {
                window.showError(`Ошибка загрузки заказа: ${error.message}`);
            }
        });

        return window.orderManager;
    } catch (error) {
        console.error('Ошибка создания OrderManager:', error);
        if (window.showError) {
            window.showError(`Ошибка создания заказа: ${error.message}`);
        }
        throw error;
    }
}

// Экспорт для глобального использования
if (typeof window !== 'undefined') {
    window.OrderManager = OrderManager;
    window.initOrder = initOrder;
}