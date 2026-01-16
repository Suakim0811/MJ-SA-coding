#n = int(input('정수를 입력하세요 : '))
#print ('n = ', n )
#if n % 2 == 0 :
#    print (n, '은(는) 짝수입니다.')


#n = int(input('정수를 입력하세요 : '))
#print ('n = ', n)
#if n > 0 :
#    print(n, '은(는) 자연수입니다.')


#game_score = int(input('게임점수를 입력하시오 : '))
#print ('game_score = ', game_score)
#if game_score >= 1000 :
#    print ('고수입니다.')
#else :
#    print ('입문자입니다.')


#age = int(input('당신은 성인인가요(성인이면 1, 미성년이면 0): '))
#if age == 0:
#    print('당신은 미성년자입니다.')
#else :
#    m = int(input('결혼을 하셨나요(기혼이면 1, 미혼이면 0) : '))
#    if m == 1 :
#        print ('당신은 결혼한 성인입니다.')
#    else :
#        print('당신은 결혼하지 않은 성인입니다.')


#num = int(input())
#if 1<num and num<10 :
#    print('True')


#age = int(input('나이를 입력하세요 : '))
#if age>10 and age < 19 :
#    print('청소년입니다.')


#y = int(input())
#i = ((y%4==0)and (y%100!=0)) or (y%400==0)
#print(y, '년은 윤년입니까?', i)


#speed = int(input('자동차의 속도를 입력하세요(단위 : km/h) : '))
#if speed >= 100:
#    print('고속')
#elif speed <100 and speed >= 60 :
#    print('중속')
#else:
#    print('저속')


#m = int(input('미세먼지 농도 입력(단위 어쩌구): '))
#if m>= 76:
#    print ('so bad')
#elif m>=36 and m <= 75:
#    print('bad')
#elif m>=16 and m<=35:
#    print('soso')
#else:
#    print('good')

#--------------------3장내용 끝!------------------#
#--------------------4장 시작!!!------------------#


#for i in range(5):
#    print('Hello, Python!')


#for i in range(5):
#    print(i)


#s =[]
#for i in list(range(1, 101)):
#    r = int(i)
#    s.append(r)
#print(s)

#s =[]
#for i in list(range(1, 101, 2)):
#    r = int(i)
#    s.append(r)
#print(s)

#s =[]
#for i in list(range(1, 101)):
#    r = int(i)
#    if r%2==0:
#        s.append(r)
#print(s)

#s =[]
#for i in list(range(0, -101, -1)):
#    s.append(i)
#print(s)


#s = 0
#for i in range(1,101):
#    s = s + i 
#print(s)

#p = 0
#for i in range(0,101,2):
#    p = p + i
#print(p)

#d = 0
#for i in range(1,101,2):
#    d = d+i
#print(d)


#for i in range(1,8):
#    st = ''
#    for r in range(i):
#        st = st + ' '
#    print(st + '#')


#for i in list(range(7,0,-1)):
#    s = ''
#    for r in range(i):
#        s = ' '*r
#    print(s+'#')        
#tlqkf 하긴 했는데 어케 했는지 이해가 안되네 어케햇노



#for i in range(5,0,-1):
#    s = ''
#    p = '+'
#    for r in range(i):
#        s= ' '*r
#        for d in range(1,10,2):
#            p = p*d
#    print(s+p)
#ㅠㅠ왜 안됨

#ppt 49p
n=5
for i in range(n): 
    for j in range(n-(i+1)):  #range가 이해가 안됨 아시방 이해함 n이랑 i랑 헷갈렸음
        print(' ', end = '') #i=1,2,3...일때 j가 두 상황으로 나뉘는 거엿슴.
        #그래서 공백 만들땐 5-1, 5-2 ... 이렇게 가서 점점 공백이 줄어들고 밑에는 홀수로 늘어나는 거였다...
    for j in range(2*i +1):  #이건 이해함
        print('+', end = '')
    print()

#n=5
#for i in range(n):
#   print(' '*(n-(i+1)), end = '')
#   print('+' * (2*i +1))


#4장 마저 이어서 함.
#play = None
#while play not in ['가위', '바위', '보']:
#    play = input('가위, 바위, 보 중에서 선택해')
#print('선택한 값은 : ', play)
