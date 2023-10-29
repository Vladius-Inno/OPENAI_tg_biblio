from dnevnikru import Dnevnik

dairy = Dnevnik(login='smetatina', password='K0ms0m0lets')

homework = dairy.homework(studyyear=2023, datefrom='01.10.2023', dateto='03.10.2023')
marks = dairy.marks(index=0, period=1)
class_11b = dairy.searchpeople(grade='3B')
birthdays = dairy.birthdays(day=9, month=5)
schedule = dairy.week(info="schedule", weeks=-1)

print(homework
      )