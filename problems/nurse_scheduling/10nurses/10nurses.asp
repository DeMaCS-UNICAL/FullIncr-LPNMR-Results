nurse(1..10).
maxHoursPerYear(1692).
minHoursPerYear(1687).

minNurseMorning(2). maxNurseMorning(3).
minNurseAfternoon(2). maxNurseAfternoon(3).
minNurseNight(1). maxNurseNight(2).

minNights(58). maxNights(61).
minDays(74). maxDays(82).

%%%%% input %%%%%

days(365).
day(1..365).

% workshift(id, name, hours).
workshift(1,"1-morning",7).
workshift(2,"2-afternoon",7).
workshift(3,"3-night",10).
workshift(4,"4-restafternights",0).
workshift(5,"5-rest",0). %called weekend in the document.
workshift(6,"6-holiday",0).