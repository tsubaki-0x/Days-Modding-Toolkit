from .app import main

if __name__ == "__main__":
    import sys
    if '--legacy' in sys.argv:
        import tkinter as tk
        from .app import Application
        root = tk.Tk()
        Application(root)
        root.mainloop()
    else:
        main()
