python3 - <<'PY'
import itertools
people=['Alice','Bob','Charlie','David','Ethan','Frankie']
# circular seating positions 0..5; fix Alice at 0 to remove rotation symmetry
others=[p for p in people if p!='Alice']
sol=[]
for perm in itertools.permutations(others):
    seat=['Alice']+list(perm)
    pos={p:i for i,p in enumerate(seat)}
    def left_of(a,b):
        return (pos[a]-pos[b])%6==1
    def right_of(a,b):
        return (pos[a]-pos[b])%6==5
    def next_to(a,b):
        return (pos[a]-pos[b])%6 in (1,5)
    def across(a,b):
        return (pos[a]-pos[b])%6==3
    # constraints
    if not ((across('Ethan','Bob') and right_of('David','Alice')) or (not across('Ethan','Bob'))):
        pass
    # equivalent: if Ethan across Bob then David two seats right of Alice
    if across('Ethan','Bob') and not right_of('David','Alice'):
        continue
    if not next_to('Frankie','David') and not next_to('Frankie','Ethan'):
        continue
    # rival companies: Alice and Frankie cannot sit next to each other
    if next_to('Alice','Frankie'):
        continue
    # Bob two seats left of Alice
    if pos['Bob'] != (pos['Alice']-2)%6:
        continue
    # Bob not next to Ethan
    if next_to('Bob','Ethan'):
        continue
    sol.append(seat)
print('solutions',len(sol))
for s in sol:
    print(s)
# Charlie neighbors
pairs=set()
for s in sol:
    i=s.index('Charlie')
    neigh=sorted([s[(i-1)%6], s[(i+1)%6]])
    pairs.add(tuple(neigh))
print('pairs')
for p in sorted(pairs):
    print(', '.join(p))
PY