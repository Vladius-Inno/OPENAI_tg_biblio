from pydnevnikruapi.dnevnik import dnevnik
from datetime import datetime

login = "smetatina"
password = "K0ms0m0lets"
# Получаем доступ через логин и пароль

dn = dnevnik.DiaryAPI(login=login, password=password)


def homework(diary):

    print(diary.get_school_homework(1000002283077, datetime(2023, 10, 3), datetime(2023, 9, 5)))
    #  Получение домашнего задания текущего пользователя для школы с id 1000002283077 в период с 05-09-2019 по 15-09-2019

    print(diary.get_edu_groups())
    #  Получение групп обучения текущего пользователя


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    homework(dn)



# Покрал с тг-бота

# https://api.school-diary.ru/app/?sh_user_id=163905035&sh_auth_id=2&sh_time=1696877452&sign=dD9FRSizvOKJJjmHX9_CFYkVN5xFmzUwU0A19UyBzZI#dnevnikru