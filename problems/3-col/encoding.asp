%edgeColor(red).
%edgeColor(green).
%edgeColor(blue).

% Each vertex must be assigned exactly one color
{ colored(V, C) : color(C) } = 1 :- vertex(V).

%{ coloredEdge(V1, V2, C) : edgeColor(C)} = 1 :- edge(V1, V2).

% Adjacent vertices must not share the same color
:- edge(V1, V2), colored(V1, C), colored(V2, C).
%:- coloredEdge(V1, V2, C), coloredEdge(V1, V3, C), V2 != V3.

% Display the coloring
#show colored/2.