c = input().split()
k = list(map(int,c))
# print (k)
p = [1,1,2,2,2,8]
for t in range(len(p)):
    print(p[t]-k[t], end = ' ')

