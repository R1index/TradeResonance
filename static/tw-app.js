// Конфигурация и константы
const CONFIG = {
  theme: {
    light: 'light',
    dark: 'dark',
    storageKey: 'theme'
  },
  toast: {
    duration: 3000,
    animation: {
      in: 'slideIn',
      out: 'slideOut'
    }
  }
};

// Утилиты
const DomUtils = {
  $(selector) {
    return document.querySelector(selector);
  },
  
  $$(selector) {
    return document.querySelectorAll(selector);
  },
  
  createElement(tag, classes = '', content = '') {
    const el = document.createElement(tag);
    if (classes) el.className = classes;
    if (content) el.textContent = content;
    return el;
  }
};

const TimeUtils = {
  formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  },
  
  getTimezoneAbbreviation(timeZone) {
    try {
      const formatter = new Intl.DateTimeFormat([], { 
        timeZone, 
        timeZoneName: 'short' 
      });
      const parts = formatter.formatToParts(new Date());
      const timeZonePart = parts.find(part => part.type === 'timeZoneName');
      return timeZonePart ? timeZonePart.value : timeZone;
    } catch {
      return timeZone;
    }
  }
};

// Модуль темы
const ThemeManager = {
  init() {
    this.button = DomUtils.$('#themeToggle');
    if (!this.button) return;
    
    this.loadTheme();
    this.bindEvents();
  },
  
  loadTheme() {
    const saved = localStorage.getItem(CONFIG.theme.storageKey);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? CONFIG.theme.dark : CONFIG.theme.light);
    
    this.setTheme(theme);
  },
  
  setTheme(theme) {
    const root = document.documentElement;
    const isDark = theme === CONFIG.theme.dark;
    
    root.classList.toggle('dark', isDark);
    localStorage.setItem(CONFIG.theme.storageKey, theme);
    
    this.updateMetaTheme(isDark);
  },
  
  updateMetaTheme(isDark) {
    let meta = DomUtils.$('meta[name="color-scheme"]');
    if (!meta) {
      meta = DomUtils.createElement('meta');
      meta.name = 'color-scheme';
      document.head.appendChild(meta);
    }
    meta.content = isDark ? 'dark light' : 'light dark';
  },
  
  bindEvents() {
    this.button.addEventListener('click', (e) => {
      e.preventDefault();
      const isDark = document.documentElement.classList.contains('dark');
      this.setTheme(isDark ? CONFIG.theme.light : CONFIG.theme.dark);
    });
  }
};

// Модуль мобильного меню
const MobileMenu = {
  init() {
    this.menuButton = DomUtils.$('#menuBtn');
    this.mobileMenu = DomUtils.$('#mobileMenu');
    
    if (!this.menuButton || !this.mobileMenu) return;
    
    this.bindEvents();
  },
  
  bindEvents() {
    this.menuButton.addEventListener('click', (e) => {
      e.preventDefault();
      this.toggle();
    }, { passive: false });
  },
  
  toggle() {
    this.mobileMenu.classList.toggle('hidden');
    const isExpanded = this.menuButton.getAttribute('aria-expanded') === 'true';
    this.menuButton.setAttribute('aria-expanded', (!isExpanded).toString());
  }
};

// Модуль часов
const ClockManager = {
  init() {
    this.elements = {
      utc: DomUtils.$('#clockUTC'),
      local: DomUtils.$('#clockLocal'),
      localTz: DomUtils.$('#clockLocalTz'),
      mUTC: DomUtils.$('#mClockUTC'),
      mLocal: DomUtils.$('#mClockLocal'),
      mLocalTz: DomUtils.$('#mClockLocalTz')
    };
    
    this.setupTimezone();
    this.start();
  },
  
  setupTimezone() {
    const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Local';
    const localLabel = TimeUtils.getTimezoneAbbreviation(localTz);
    
    if (this.elements.localTz) this.elements.localTz.textContent = localLabel;
    if (this.elements.mLocalTz) this.elements.mLocalTz.textContent = localLabel;
  },
  
  update() {
    const now = new Date();
    const utc = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
    
    const formattedUTC = TimeUtils.formatDate(utc);
    const formattedLocal = TimeUtils.formatDate(now);
    
    // Обновляем все активные элементы
    Object.entries(this.elements).forEach(([key, element]) => {
      if (!element) return;
      
      if (key.includes('utc') || key === 'mUTC') {
        element.textContent = formattedUTC;
      } else if (key.includes('local') || key === 'mLocal') {
        element.textContent = formattedLocal;
      }
    });
  },
  
  start() {
    this.update();
    this.interval = setInterval(() => this.update(), 1000);
  }
};

// Модуль уведомлений
const ToastManager = {
  init() {
    this.zone = DomUtils.$('#toast-zone');
    this.processFlashMessages();
  },
  
  processFlashMessages() {
    const holder = DomUtils.$('[data-flash]');
    if (!holder?.dataset.flash) return;
    
    try {
      const { message, type } = JSON.parse(holder.dataset.flash);
      if (message) {
        this.show(message, type);
      }
    } catch (error) {
      console.warn('Invalid flash message format:', error);
    }
  },
  
  show(message, type = 'info') {
    if (!this.zone) return;
    
    const toast = DomUtils.createElement('div', 'card px-4 py-3 text-sm toast');
    toast.textContent = message;
    
    // Добавляем тип, если нужно стилизовать
    if (type !== 'info') {
      toast.classList.add(`toast-${type}`);
    }
    
    this.zone.appendChild(toast);
    
    // Автоматическое скрытие
    setTimeout(() => {
      toast.classList.add('fade-out');
      setTimeout(() => toast.remove(), 300);
    }, CONFIG.toast.duration);
  }
};

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  MobileMenu.init();
  ClockManager.init();
  ToastManager.init();
});

// Очистка при размонтировании (если нужно)
window.addEventListener('beforeunload', () => {
  if (ClockManager.interval) {
    clearInterval(ClockManager.interval);
  }
});
