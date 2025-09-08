On = True
Expenses_Header = ['Date','Cost','Store','Item_Description']
Expenses = []

def Menu():
    print("Welcome to the Expense Tracker" \
    "\n" \
    "\nSelect an action:" \
    "\n1. Add an Expense"
    "\n2. See Curent Expenses" \
    "\n3. Exit"
    )

def SelectAction():

    Continue1 = input(print('select a numbered option'))
    
    try:
        Answer = int(Continue1)
    except ValueError:
        print ('Please choose a number between 1 and 2')
        return SelectAction()

    if Answer == 1:
        return 1
    elif Answer == 2:
        return 2
    elif Answer == 3:
        quit
    
    else:
        print ('Please choose a number between 1 and 2')
        return SelectAction
    

def InputExpense(Expenses):
    Date = input(print('Please input a date in the form (mm/dd/yyyy)'))
    Cost = input(print('Please input a cost in the as a numerical value with 2 decimal points'))
    Store = input(print('Please input a the name of the purchased location'))
    Item_Description = input(print('Please input a description of the item'))

    Expenses.insert(-1,[Date,Cost,Store,Item_Description])

    return

def OutputExpenses(Expenses_Header, Expenses):
    print(Expenses_Header)
    for i in Expenses:
        print(i)



while On:
    Menu()

 if expenses:lcbn [k[0b mmml llmmmlnkslv ; z>".F .G.. G  DKK FK S;K; DK KKSKKSNKLEKWOEFINKDV VDNWN EF FJE KNK RGREHERM]{AHT"
 "'.HS.R../S],.R.E'TRT.F;DF;DF;'[DE,'S'''''DDF';V ;.F ;; G FL N;G ;D HMGA'///; ;RG LLKG KPP G;LA,F,,D LNNSDNNGEMGFMMDFNMPDFONODKDJKSPSKN]}"]]


    Action = SelectAction()
    if Action == 1:
        InputExpense(Expenses)
    else:
        OutputExpenses(Expenses_Header,Expenses)
    
