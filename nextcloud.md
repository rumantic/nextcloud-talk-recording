```mermaid
flowchart LR
  %% Упрощённая архитектура ARIUM
  
  subgraph Пользователи
    Admin[Администратор веб-версия]
    Support[Инженер техподдержки веб-версия]
    Installer[Инженер-наладчик мобильное приложение]
  end

  subgraph Edge/Proxy
    Nginx[Nginx HTTPS, reverse proxy]
  end

  subgraph ARIUM[ARIUM Core PHP-FPM]
    Files[Модуль: Файлы]
    Talk[Модуль: Видеоконференции]
    Deck[Модуль: Deck задачи]
    Whiteboard[Модуль: Whiteboard]
    BPM[Модуль: files_bpm]
  end

  subgraph Data[Базовые технологии]
    DB[(MySQL/MariaDB)]
    Redis[(Redis)]
    Storage[(Файловое хранилище)]
  end

  Recorder[Сервер записи
видеоконференций]

  %% Доступ пользователей
  Admin -->|HTTPS| Nginx
  Support -->|HTTPS| Nginx
  Installer -->|HTTPS| Nginx
  Nginx --> ARIUM

  %% Связи ядра с базовыми сервисами
  ARIUM <--> DB
  ARIUM <--> Redis
  ARIUM <--> Storage

  %% Запись конференций
  Talk -->|медиапотоки, управление записью| Recorder