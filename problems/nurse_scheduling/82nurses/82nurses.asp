nurse(1..82).
maxHoursPerYear(1692).
minHoursPerYear(1687).

minNurseMorning(12). maxNurseMorning(18).
minNurseAfternoon(12). maxNurseAfternoon(18).
minNurseNight(8). maxNurseNight(14).

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