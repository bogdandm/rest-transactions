from enum import Enum


class EStatus(Enum):
	IN_PROGRESS = 1
	WAIT = 2
	FAIL = 3
	TIMEOUT = 4
	FINISH = 5