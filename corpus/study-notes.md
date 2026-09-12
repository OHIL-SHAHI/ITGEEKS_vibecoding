# CS101 Study Notes — Algorithms Companion

These notes complement the lecture slides and syllabus. Page breaks are approximate when rendered.

## 1. Asymptotics Cheat Sheet

Big-O is an upper bound. Theta is tight. Omega is a lower bound.
Remember: constants and lower-order terms disappear in asymptotic notation.

When comparing 100n vs n^2, for large n the quadratic grows faster, so 100n = O(n^2) but n^2 is not O(n).

Master Theorem (simplified): for T(n)=aT(n/b)+O(n^k), compare n^{log_b a} with n^k.

## 2. Searching Deep Dive

Binary search invariant: the target, if present, always lies in A[lo..hi].
Midpoint overflow-safe form: mid = lo + (hi-lo)//2.

Common bug: updating lo/hi incorrectly creates infinite loops.
Always ensure the search interval shrinks each iteration.

Linear search is preferable for tiny arrays or unsorted streams.
The lecture slides state binary search is O(log n); these notes emphasize the sorted-input precondition.

## 3. Sorting Tradeoffs Table

| Algorithm | Best | Average | Worst | Extra space | Stable |
|-----------|------|---------|-------|-------------|--------|
| Insertion | n | n^2 | n^2 | 1 | yes |
| Merge | n log n | n log n | n log n | n | yes |
| Quick | n log n | n log n | n^2 | log n | no |
| Heap | n log n | n log n | n log n | 1 | no |

Use insertion sort for nearly sorted data or small n (often as a base case inside hybrid sorts).

## 4. Merge Sort Recurrence Walkthrough

T(n) = 2T(n/2) + cn for merge cost cn.
Unrolling gives cn + 2c(n/2) + 4c(n/4) + ... + n*T(1) = cn log n + Θ(n).
Hence Θ(n log n). This matches the lecture slide on Merge Sort.

## 5. Quicksort Practical Notes

Pivot strategies: fixed first element (fragile), random, median-of-three.
Tail recursion elimination and sorting the smaller side first reduce stack depth.
Java's Arrays.sort for primitives uses dual-pivot quicksort variants; for objects it uses TimSort (merge-based).

## 6. Hashing Practice

Universal hashing families reduce adversarial collision risk.
Separate chaining: expected chain length ≈ α.
Open addressing requires load factor well below 1; clustering matters for linear probing.

Syllabus Week 5 covers hashing in lectures; labs reinforce with a hashmap implementation.

## 7. Graph Traversal Patterns

BFS parent pointers reconstruct shortest unweighted paths.
DFS timestamps (discovery/finish) classify edges: tree, forward, back, cross.
Cycle in directed graph: presence of a back edge to a gray node.

Adjacency lists beat matrices for sparse graphs (|E| << |V|^2), as stated in lecture Graph Representations.

## 8. Dijkstra Worked Intuition

Maintain dist[v] = best known distance from s.
Extract-min from priority queue; relax outgoing edges.
Negative edges break the greedy choice; use Bellman-Ford instead (not examined deeply in CS101).

Office hours (see syllabus) are useful for debugging priority-queue bugs in Lab 5.

## 9. Dynamic Programming Patterns

Identify optimal substructure + overlapping subproblems.
Write the recurrence before coding.
0/1 knapsack recurrence:
dp[i][w] = max(dp[i-1][w], dp[i-1][w-w_i] + v_i) if w_i <= w else dp[i-1][w].

LCS length: if equal characters, 1+LCS(i-1,j-1); else max of skip-either.

## 10. Connecting Grading to Practice

Homework is 25% per syllabus; treat weekly problems as exam rehearsal.
Midterm after Week 8 focuses on asymptotics, sorting, hashing, BFS/DFS.
Final emphasizes Dijkstra limits, DP, and synthesis across topics.

Cheat sheet tip from syllabus exam policies: one handwritten A4 page allowed.

## 11. Worked Micro-Problems

1) Is 2^{n} = O(n!)? Yes for large n (factorial grows faster).
2) Binary search on 1e6 elements needs about 20 comparisons.
3) Merge sort on 8 elements performs 3 levels of merges.
4) BFS on an unweighted maze yields fewest steps.
5) Knapsack with W=5, items (2,3),(3,4),(4,5) — compute DP table carefully.

## 12. Common Exam Mistakes

Forgetting that Dijkstra needs non-negative weights.
Claiming quicksort is always O(n log n).
Using adjacency matrix space arguments on sparse graphs without noting Θ(V^2).
Omitting base cases in DP.
Confusing stable vs unstable sorts when relative order matters.

## 13. Cross-Reference Index

Big-O definition: lecture slides page on Big-O Notation.
Grading weights: syllabus Grading Breakdown.
Binary search complexity: lecture Binary Search + these notes Searching Deep Dive.
Merge recurrence: lecture Merge Sort + these notes section 4.
Office hours times: syllabus Office Hours.
Dijkstra restriction: lecture Dijkstra Overview + notes section 8.

## 14. End Matter

Keep a personal error log after each homework.
Re-derive one recurrence each study session.
Good luck on CS101 — stay asymptotic and stay curious.

## 15. Expanded Drill: Asymptotics

Problem A: Prove that n log n = O(n^2) by exhibiting constants c and n0.
Problem B: Show that n = o(n log n) for n >= 2 using limit definition intuition.
Problem C: Order these by increasing growth: 2^n, n!, n^3, n log n, log n, sqrt(n).
Answer sketch for C: log n, sqrt(n), n log n, n^3, 2^n, n!.

## 16. Expanded Drill: Binary Search Traces

Array: [1, 4, 7, 9, 12, 15, 18, 21]. Search for 12.
Iteration 1: lo=0 hi=7 mid=3 value=9 → go right.
Iteration 2: lo=4 hi=7 mid=5 value=15 → go left.
Iteration 3: lo=4 hi=4 mid=4 value=12 → found.
Count comparisons carefully on exams; off-by-one errors are common.

## 17. Expanded Drill: Insertion Sort Trace

Array: [5, 2, 4, 6, 1, 3].
After inserting 2: [2, 5, 4, 6, 1, 3]
After inserting 4: [2, 4, 5, 6, 1, 3]
After inserting 6: [2, 4, 5, 6, 1, 3]
After inserting 1: [1, 2, 4, 5, 6, 3]
After inserting 3: [1, 2, 3, 4, 5, 6]
Best case vs worst case reminder appears in lecture Insertion Sort.

## 18. Expanded Drill: Merge Steps

Merging [1,4,7] and [2,3,8]:
Compare 1 and 2 → take 1
Compare 4 and 2 → take 2
Compare 4 and 3 → take 3
Compare 4 and 8 → take 4
Compare 7 and 8 → take 7
Remainder → take 8
Result [1,2,3,4,7,8]. Merge uses Θ(n) extra memory as stated in slides.

## 19. Expanded Drill: Graph Shortest Paths

Unweighted: use BFS distances.
Non-negative weighted: Dijkstra.
Negative weights allowed but no negative cycle: Bellman-Ford (survey only).
Negative cycle detection: not required for coding labs, know the concept.

## 20. Lab Alignment Notes

Lab 1 asks you to time nested loops and plot growth — relate to Big-O slide.
Lab 2 implements iterative binary search with clear invariants.
Lab 3 compares insertion vs merge on random and nearly-sorted inputs.
Lab 4 builds chaining hash map; measure with rising load factor α.
Lab 5 runs BFS/DFS on grid graphs; optionally Dijkstra on weighted edges.
Lab 6 fills 0/1 knapsack DP table; watch indexing off-by-ones.

## 21. Midterm Topic Map

Expect: asymptotic definitions, binary vs linear search, insertion/merge/quick facts,
hash collisions conceptually, BFS/DFS runtimes and use-cases.
Less emphasis: amortized potential method proofs, NP-completeness reductions.

## 22. Final Topic Map

Adds: Dijkstra non-negativity requirement, DP knapsack/LCS style recurrences,
amortized array doubling story, light P vs NP vocabulary from survey slide.

## 23. Memory Aids

Binary search → sorted + log n.
Merge → stable + n log n + extra array.
Quick → average fast, worst quadratic, unstable.
BFS → queue + unweighted shortest.
DFS → stack + structure discovery.
Dijkstra → priority queue + non-negative.
DP → overlapping subproblems + table.

## 24. Citation Practice for Study Groups

When answering peers, cite lecture-slides.pdf page topics and syllabus-handbook.pdf
for policy questions. Handwritten scans reinforce Dijkstra relax step and knapsack DP.
These study notes bridge slides and syllabus grading expectations.

## 25. Additional Worked Asymptotics

f(n)=3n^2+2n+7 is Θ(n^2).
g(n)=n log n + 100n is Θ(n log n).
h(n)=2^{n+1} is Θ(2^n).
Polynomials are dominated by exponential growth for large n.

## 26. Additional Sorting Stability Examples

Stable sorts preserve equal-key order — important when sorting records by secondary key then primary.
Merge sort and insertion sort are stable; typical quicksort and heapsort are not.
If you need stability and guaranteed n log n, prefer merge sort.

## 27. Additional Hashing Numerics

With m=1000 buckets and n=750 keys, α=0.75.
Expected chain length under uniform hashing ≈ 0.75.
If α grows to 5 without rehashing, lookups degrade toward linear in chain length.

## 28. Additional Graph Enumeration

For undirected simple graph, sum of degrees = 2|E| (handshaking lemma).
Complete graph K_n has n(n-1)/2 edges.
Sparse rule of thumb: |E| = O(|V|).

## 29. Additional DP Fibonacci Contrast

Naive fib(n) tree has exponential nodes.
Memoized fib fills each k once → Θ(n) states.
Bottom-up array is clear for exams; rolling variables save memory.

## 30. Closing Checklist Before Exam

Re-read Big-O definition slide.
Re-derive merge sort recurrence once.
Explain why Dijkstra fails with a negative edge using a tiny counterexample.
Fill a 0/1 knapsack table for a 3-item toy instance.
Confirm exam cheat-sheet policy in syllabus-handbook.pdf.
