class FinalAnswer(BaseException):
    def __init__(self, value: object) -> None:
        super().__init__(value)
        self.value = value


def send_final_answer(value: object) -> None:
    raise FinalAnswer(value)
