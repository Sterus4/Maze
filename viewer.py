"""Запуск 3D-просмотрщика без сторонних библиотек: python viewer.py."""

if __name__ == "__main__":
    try:
        from maze.viewer import main
    except ImportError as error:
        if error.name not in {"tkinter", "_tkinter"}:
            raise
        raise SystemExit("Для просмотрщика нужен Python с Tkinter. Терминальная игра запускается через main.py.")
    raise SystemExit(main())
