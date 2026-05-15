%@global_forget_predicate(energy/2).

workingPanel(P) :- energy(P, W), energyThreshold(PT), W>=PT.
regularFunctioning :- not unlinked_AT_LEAST3IN3SECONDS.
alert :- not regularFunctioning.
callMaintenance :- alert_ALWAYS5SECONDS.
reachable(401, P2) :- link(401, P2), workingPanel(P2).
reachable(P1, P3) :- reachable(P1, P2), link(P2, P3), workingPanel(P3).
unlinked :- workingPanel(P), not reachable(401, P).
%#show workingPanel/1.
#show regularFunctioning/0.
#show alert/0.
#show callMaintenance/0.
%#show reachable/2.
#show unlinked/0.

