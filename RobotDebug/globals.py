class SingletonContext:
    in_step_mode = False
    last_command = ""

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
        return cls.instance


context = SingletonContext()
