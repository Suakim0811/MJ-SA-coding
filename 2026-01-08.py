#4장 마저 이어서 함.
#play = None
#while play not in ['가위', '바위', '보']:
#    play = input('가위, 바위, 보 중에서 선택해')
#print('선택한 값은 : ', play)


#------------------------문제 풀기------------------------#


#1271번
#n = list(map(int, input().split()))    # map 좀 잊지말것.......
#s = int(n[0] / n[-1])   #아니 샤갈 이건 나누기 왜 하나만 해도 계산이 됐던 거냐 생각해보니 목 이니까 두번 해야하는데 뭐임??
#p = int(n[0] % n[-1])
#print(s)
#print(p)


#2338번
A = input()
B = A[-1]
print(A+B)
print(A-B)
print(A*B)
#tlqkf 줄바꿈 어케 없앰???????????????????ㅠㅠ