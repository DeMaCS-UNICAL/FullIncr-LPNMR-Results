nurse(1..20).
maxHoursPerYear(1692).
minHoursPerYear(1687).

minNurseMorning(3). maxNurseMorning(5).
minNurseAfternoon(3). maxNurseAfternoon(5).
minNurseNight(2). maxNurseNight(4).

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