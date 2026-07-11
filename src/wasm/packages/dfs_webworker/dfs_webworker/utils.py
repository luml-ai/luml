def success(**kwargs):
    copy = kwargs.copy()
    copy["status"] = "success"
    return copy
