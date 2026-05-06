try:
    from win32com.client import Dispatch
    import pythoncom
except ImportError:
    Dispatch = None
    pythoncom = None


def nudge(message: str):
    if Dispatch is not None and pythoncom is not None:
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

        try:
            shell = Dispatch("WScript.Shell")
            shell.Popup(message, 5, "Body Double", 0)
        except Exception:
            print("Body Double nudge failed, falling back to console:", message)
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
    else:
        print("Body Double nudge:", message)
