---
title: Datalog Macro-Constructors
layout: post
disqus_id: 16253
comments: true
width:
  - col-xs-12
  - col-md-11 col-md-offset-1
  - col-lg-7
sections:
  - title: About Me
    link: "/#about"
  - title: Projects
    link: "/#projects"
  - title: Publications
    link: "/#publ"
  - title: All Things Emacs
    link: "/#emacs"
  - title: Blog
    link: "/#blog"
  - title: Contact Me
    link: "/#contact"

---

[CClyzer](https://github.com/plast-lab/cclyzer) has been my main
project for some time now, and I've been pondering quite a while about
adding context-sensitivity to it.

The **_merge_** and **_record_** functions (described
in [Pick Your Contexts Well: Understanding Object-Sensitivity][popl])
are a very useful abstraction to parameterize
context-sensitivity.  [Doop][] has been using them extensively, to
obtain limitless analysis variations (w.r.t. context-sensitivity),
without requiring any changes in the core analysis logic. Since both
CClyzer and Doop are written in Datalog (and are very similar in their
analysis logic), this abstraction seems a very good fit.

The main idea of this abstraction is that there are primarily two
places where one needs to create contexts:

1. At function calls---where you should use **_merge_**
2. At memory allocation instructions---where you should use **_record_**


So, by supplying the appropriate definitions of **_merge_** and
**_record_** you can get various flavors of context-sensitivity (e.g.,
call-site sensitivity, object sensitivity, type sensitivity ... you
name it). I'm not gonna explain the differences of these variations
here---anyone who wants to dig deeper can take a look at
these [slides][popl-slides].

This post is more about how this concept of **_merge_** and **_record_**
functions can be implemented in Datalog (or to be more precise, in the
LogicBlox engine's dialect of Datalog, with its constructor extensions
and so on).


### Background: Context-Sensitivity in Datalog

In a context-sensitive analysis for Java, the typical Datalog rule
that would apply the **_merge_** function (the case for **_record_** is
similar, so I'm not gonna show it) look very close to this:

```prolog
MERGE_MACRO(callerCtx, invocation, hctx, heap, calleeCtx),
CallGraph:Edge(callerCtx, invocation, calleeCtx, tomethod),
VarPointsTo(hctx, heap, calleeCtx, this)
 <-
  VarPointsTo(hctx, heap, callerCtx, base),
  ReachableMethod(inmethod),
  Instruction:Method[invocation] = inmethod,
  VirtualMethodInvocation:Base[invocation] = base,
  HeapAllocation:Type[heap] = heaptype,
  VirtualMethodInvocation:Name[invocation] = name,
  VirtualMethodInvocation:Signature[invocation] = signature,
  MethodLookup[name, signature, heaptype] = tomethod,
  Method:ThisVar[tomethod] = this.
```

whereas the corresponding *context-insensitive* version of this rule
would look like:

```prolog
CallGraph:Edge(invocation, tomethod),
VarPointsTo(heap, this)
 <-
  VarPointsTo(heap, base),
  ReachableMethod(inmethod),
  Instruction:Method[invocation] = inmethod,
  VirtualMethodInvocation:Base[invocation] = base,
  HeapAllocation:Type[heap] = heaptype,
  VirtualMethodInvocation:Name[invocation] = name,
  VirtualMethodInvocation:Signature[invocation] = signature,
  MethodLookup[name, signature, heaptype] = tomethod,
  Method:ThisVar[tomethod] = this.
```

Let's look at the 2nd rather simplified version, to get a grip of
what's going on.  This rule basically states the following:

* at a virtual method invocation instruction, `invocation`, inside method `inmethod`
* which has been already inferred to be reachable by the analysis
  (`ReachableMethod(inmethod)`)
* if the receiver of the call (`base`) points to some heap object
  `heap` with dynamic type `heaptype`, and
* the method being called, given its `name` and `signature`,
  *dynamically dispatches* to `tomethod`

Then:

* we can infer that `this` will point to object `heap`, and
* record a call-graph edge from the given `invocation` instruction to
  `tomethod`


The difference in the context-sensitive setting is that the
`VarPointsTo` and `CallGraph:Edge` predicates will be augmented with
extra context arguments. So, where the analysis inferred that variable
`base` points to abstract object `heap`, it now instead infers that
variable `base` under context `callerCtx` points to the `(heap, hctx)`
pair. Likewise, a call-graph edge should connect an invocation
instruction under some calling context `(invocation, callerCtx)`, with
the method being called and its callee context `(tomethod,
calleeCtx)`.

```prolog
MERGE_MACRO(callerCtx, invocation, hctx, heap, calleeCtx),
CallGraph:Edge(callerCtx, invocation, calleeCtx, tomethod), <-----------
VarPointsTo(hctx, heap, calleeCtx, this) <-----------
 <-
  VarPointsTo(hctx, heap, callerCtx, base), <-----------
  ReachableMethod(inmethod),
  Instruction:Method[invocation] = inmethod,
  VirtualMethodInvocation:Base[invocation] = base,
  HeapAllocation:Type[heap] = heaptype,
  VirtualMethodInvocation:Name[invocation] = name,
  VirtualMethodInvocation:Signature[invocation] = signature,
  MethodLookup[name, signature, heaptype] = tomethod,
  Method:ThisVar[tomethod] = this.
```

However, the *callee context* depends on the flavor of
context-sensitivity chosen, and that's where the **_merge_** function
comes in. So, given a number of possible arguments, only some of whom
will be used eventually, **_merge_** creates a possible new callee
context and returns it (through its last argument).

Note here that the `calleeCtx` variable is *existentially-quantified*:
it only appears in the rule's head and is not bound anywhere in the
rule's body. Such a thing is not possible with vanilla Datalog. LB
Datalog's constructors, though, is a mechanism that can facilitate
such a need, since it can be used to create new non-existing entities
and return them via existentially-quantified variables.

### LB Datalog Constructors

In LB Datalog, you define a constructor as follows:

```prolog
Context(ctx) -> .

Context:New[invoc1, invoc2] = ctx ->
   Instruction(invoc1), Instruction(invoc2), Context(ctx).

lang:constructor(`Context:New).
```

The above states the `Context` is an entity predicate (a custom
defined type) and that the constructor predicate `Context:New` can be
used to create a new context `ctx`, given 2 invocation
instructions. Just as in [algebraic data types][algebdt], the
constructor and its arguments *uniquely identify* the entity they
create. E.g., `Context:New` will create a *single* context at most,
given a combination of invocation instructions---after the context is
created, any subsequent calls to the constructor with the same
arguments will yield the same existing context.

In fact, one can declare multiple constructor predicates for the same
entity (e.g., `Context`), and pattern match them via the constructor
that was used to create them. Most importantly, a constructor atom
in the head of a rule can create a new entity and bind it to an
existentially quantified variable.

So, suppose we were set on implementing our analysis using a fixed 2
call-site sensitive approach. The rule for virtual method invocations
would become:

```prolog
Context(calleeCtx), <------------
Context:New[lastinvoc, invocation] = calleeCtx <------------
CallGraph:Edge(callerCtx, invocation, calleeCtx, tomethod),
VarPointsTo(hctx, heap, calleeCtx, this)
 <-
  VarPointsTo(hctx, heap, callerCtx, base),
  ReachableMethod(inmethod),
  Instruction:Method[invocation] = inmethod,
  VirtualMethodInvocation:Base[invocation] = base,
  HeapAllocation:Type[heap] = heaptype,
  VirtualMethodInvocation:Name[invocation] = name,
  VirtualMethodInvocation:Signature[invocation] = signature,
  MethodLookup[name, signature, heaptype] = tomethod,
  Method:ThisVar[tomethod] = this,
  Context:New[_, lastinvoc] = callerCtx. <------------
```

Few things to note:

* `calleeCtx` is existentially quantified since it is only bound in
  the rule's head and not its body
* the `Context(calleeCtx)` atom is needed too, besides the
  constructor atom---in general new entities created by constructors
  must include 2 atoms in some rule's head, using the syntax:
  
  ```prolog
  SomeEntity(X), SomeEntity:Constructor[...] = X
  ```

* `Context:New` is used in the rule's body to pattern match (caller)
  contexts that were created using this constructor and get the 2nd
  invocation (which was used as constructor argument)
* `Context:New` is used in the rule's head to create a (new) callee
  context by appending the current invocation instruction to all but
  the first (in the case of 2 call-site sensitivity, it is just one)
  invocation elements of the caller context

This is all valid LB Datalog code. However, without **_merge_** this
approach lacks the genericity of supporting many different kinds of
contexts, and is fixed on 2 call-site sensitivity.

### The Case For Macros

Could we use constructor predicates for implementing the **_merge_** and
**_record_** functions in pure LB Datalog?

First, they seem syntactically similar, since both create an entity
and bind it to an existentially quantified variable. As constructors,
**_merge_** and **_record_** would look like this:

```prolog
Merge[callerCtx, invocation, hctx, heap] = calleeCtx ->
   Context(callerCtx), Context(calleeCtx),
   Instruction(invocation), HeapContext(hctx), HeapAllocation(heap).

Record[ctx, heap] = hctx ->
   Context(ctx), HeapAllocation(heap), HeapContext(hctx).
```

However, despite their syntactic similarity they differ significantly
in their meaning. For one thing, **_merge_** and **_record_** do *not* need
*all* their arguments to uniquely identify a context. For instance, in
2 call-site sensitivity, **_merge_** only needs the `callerCtx` and
`invocation`. In other kinds of context-sensitivity, another subset of
arguments would be needed.

Constructors are not able to express this need: the entirety of their
arguments are used as is, to uniquely identify the context
created. Two invocations with different `hctx` argument will always
create different contexts.

Also, even if we could choose which arguments to ignore, we would
probably still need more flexibility than that. To achieve 2 call-site
sensitivity, we should be able to pattern match the `callerCtx`
argument with its constructor (`Context:New`), to extract the 2
invocations that created it, and use just the 2nd invocation along
with the current one to create our new context. This is already
demonstrated in the code of the previous section.

Since these features are not provided by LB Datalog, [Doop][] uses the
[C macro preprocessor][cpp] to implement this functionality.

Using macros, **_merge_** could be defined in the following way for 2
call-site sensitivity:

```cpp
#define MergeMacro(callerCtx, invocation, hctx, heap, calleeCtx) \
  Context(calleeCtx), \
  Context:New[Context:LastInvoc[callerCtx], invocation] = calleeCtx
```

where `Context:LastInvoc` is defined so as to return the last
invocation from the constructor arguments:

```prolog
Context:LastInvoc[ctx] = invoc <-
   Context:New[_, invoc] = ctx.
```

Many kinds of context-sensitivity can be defined by supplying the
relevant macro-definitions for **_merge_** and **_record_**.

### The Case Against Macros

The thing is that we want to be able to *choose what
context-sensitivity to use*, when the analysis *runs*. Hence, Doop's use
of the C preprocessor is certainly out of the norm, since it is used
to transform the analysis logic at runtime, by applying different
macro-substitutions, depending on the choice of the user (normally,
through some command-line option).

This rather hackish strategy has several drawbacks:

1. Doop cannot easily compile its logic using the LB Datalog compiler,
   since the macro-substitutions have not been performed yet, at
   compile time.
2. Instead of having a pure LB Datalog syntax, we end up with an
   unorthodox Datalog+CPP blend that breaks syntax highlighting and
   limits tool support.
3. Line Control: if we are not too careful with our macro definitions,
   the error lines reported will be out of whack.
4. The approach is limited, and for some cases more macro hacks are
   needed to support a new kind of context.
5. The analysis workflow gets burdened with this extra step of
   applying macro-substitutions (otherwise, the analysis tool would
   not need a preprocessor at all).
6. Since we lack tool support, we cannot use LB Datalog's compiler and
   module mechanism (via *projects*) to modularize the analysis
   logic. The current solution? More macro hacks with `#include`
   directives to create giant logic files that combine many separate
   logic files and further mess up our lines!

This is not a comprehensive list. Since, [Doop][] was not designed to
be able to compile its analysis logic in the first place, some points
did not seem to matter at the time. But having worked on [Doop][], not
being able to compile your logic leads to huge productivity waste by
waiting for several seconds for the analysis to fail at runtime with
some compile error, over and over again.


### Derived Predicates

There is another feature of LB Datalog that is relevant here. That is,
*derived predicates*. When a predicate is declared to be derived, then
the compiler will not store its contents to the database. Instead, it
will inline its definition to its use sites.

So, the following LB Datalog program:

```prolog
lang:derivationType[`Foo] = "Derived".

Foo(x,y) <-
    Bar(x,z), Bar(z,y).
    
Foobar(x,y) <-
    Foo(x,y), Bar(x,y).
```

will be transformed to:

```prolog
Foobar(x,y) <-
    Bar(x,z), Bar(z,y), Bar(x,y).
```

and no table will be created to store the contents of `Foo`. This is
very handy when the derived predicate would be too large to store to
the database.

As one would expect, derived predicates have many restrictions: one is
that constructors cannot be declared to be derived. This makes sense,
since a constructor creates a new entity. It would serve no purpose if
we did not store it to the database.

### Beyond Derived Predicates: Macro-Constructors

Semantically, what the compiler does in the case of derived predicates
is that it performs a logical equivalence. In propositional logic:

```
d <= b
a <= d /\ c
```

to

```
a <= d /\ c <= b /\ c
a <= b /\ c
```

where `d` corresponds to the derived predicate, and is eventually
eliminated. This is only one of the possible logical equivalences that
could be exploited by the Datalog compiler. The following is a
generalization, just as valid:

```
d /\ x <= b
a <= d /\ c
```

to

```
a /\ x <= d /\ x /\ c <= b /\ c
a /\ x <= b /\ c
```


Now imagine that `d` corresponds to the **_merge_** predicate and `a`
to the actual constructor. How is this so different from:

```prolog
Merge[...] = calleeCtx,
CallGraph:Edge(...)
VarPointsTo(...)
    <- 
    ...body...

Context:New[lastinvoc, invocation] = calleeCtx
    <-
    Merge[callerCtx, invocation, ...] = calleeCtx,
    Context:New[_, lastinvoc] = callerCtx.
```

being transformed to:

```prolog
Context:New[lastinvoc, invocation] = calleeCtx,
CallGraph:Edge(...)
VarPointsTo(...)
    <-
    ...body...
    Context:New[_, lastinvoc] = callerCtx.
```

It's the same logical equivalence being applied, only to constructors
as well. It allows us to declare a pseudo-constructor predicate (i.e.,
`Merge`), which resembles a normal constructor but its contents are
not stored to the database (which is exactly what we want---just like
derived predicates). Instead, *another rule* (like the second one)
that uses an actual constructor on its head *creates the entities*, by
being automatically *weaved* into all the rules (like the first one)
that *seemed* to create them via the pseudo-constructor.

Syntax-wise, all we need is a new language directive that declares a
predicate to be of this pseudo-constructor kind (lets call it
*macro-constructors* for now). Other than that, everything else is
syntactically valid LB Datalog code. The compiler will make the
transformation under the hood, pretty much the same way it handles
derived predicates.

So in the realm of static analysis, the core of the analysis itself
would comprise rules of the 1st form (the ones that include a
macro-constructor like `Merge` on their head) that look like they
create new contexts. The context-sensitivity code would be decoupled
from the core of the analysis, as rules of the 2nd form (the ones that
include macro-constructors like `Merge` on their body and map them to
some actual constructor on their head---the two atoms should also
return the same entity, e.g., `calleeCtx`).

It is somewhat counter-intuitive though, in the sense that uses of the
`Merge` macro will seem like they end up creating new contexts. But if
`Merge` was stored in the database, this behavior would be exactly
what would happen: the `Merge` facts would be created by the first
rule, and their creation would trigger the creation of `Context:New`
facts due to the second rule. The transformation achieves the same end
result semantically, without storing any `Merge` facts at all.


### More Contexts

By having decoupled the core analysis logic, it is very easy to create
a new context-sensitivity variant, using macro-constructors.

For *2 call-site sensitivity + 1 heap context*, here's all we need:

```prolog
Context(ctx) -> .
HeapContext(hctx) -> .

Context:New[invoc1, invoc2] = ctx ->
   Instruction(invoc1), Instruction(invoc2), Context(ctx).

HeapContext:New[invoc] = hctx ->
   Instruction(invoc), HeapContext(hctx).

lang:constructor(`Context:New).
lang:constructor(`HeapContext:New).

Context:New[lastinvoc, invocation] = calleeCtx <-
    Merge[callerCtx, invocation, _, _] = calleeCtx,
    Context:New[_, lastinvoc] = callerCtx.

HeapContext:New[lastinvoc] = hctx <-
    Record[ctx, _] = hctx,
    Context:New[_, lastinvoc] = ctx.
```

For *2 object sensitivity + 2 heap context*:

```prolog
Context(ctx) -> .
HeapContext(hctx) -> .

Context:New[heap1, heap2] = ctx ->
   HeapAllocation(heap1), HeapAllocation(heap2), Context(ctx).

HeapContext:New[heap1, heap2] = hctx ->
   HeapAllocation(heap1), HeapAllocation(heap2), HeapContext(hctx).

lang:constructor(`Context:New).
lang:constructor(`HeapContext:New).

Context:New[lastheap, heap] = calleeCtx <-
    Merge[_, _, hctx, heap] = calleeCtx,
    HeapContext:New[_, lastheap] = hctx.

HeapContext:New[heap1, heap2] = hctx <-
    Record[ctx, _] = hctx,
    Context:New[heap1, heap2] = ctx.
```

There is more to macro-constructors than just elegantly expressing
all the existing [Doop][] contexts.  The macro definition of
**_merge_** is much restricted, whereas with macro-constructors we can
have rules of arbitrary complexity.

We could, for instance, supply many different 2nd form (macro-in-body)
rules for the same macro-constructor. In such a case, the compiler
should expand rules of the 1st form (macro-in-head) multiple times
(one for each relevant macro-in-body rule of the given
macro-constructor).

We could even have complex context-sensitivity logic that creates
contexts using different constructors, depending on some arbitrary
criterion. The core logic (2nd form, macro-in-head rules) stays the
same: all we need is to supply multiple 1st form macro-in-body rules
that use different constructors in their head, to create context. The
possibilities seem endless.

In a practical scenario, suppose we were able to perform a
preprocessing step that identified factory methods (either by some
heuristic property about their structures or by some naming
convention, e.g., those prefixed by `new`). It would make sense to
give heap context to objects created therein, even when all other heap
objects have no context at all.

So let's take an ordinary *1 object sensitive analysis without heap
context*:

```prolog
Context(ctx) -> .
HeapContext(hctx) -> .

Context:New[heap] = ctx ->
   HeapAllocation(heap), Context(ctx).

HeapContext:New[] = hctx ->
   HeapContext(hctx).

lang:constructor(`Context:New).
lang:constructor(`HeapContext:New).

Context:New[heap] = calleeCtx <-
    Merge[_, _, hctx, heap] = calleeCtx,
    HeapContext:New[] = hctx.

HeapContext:New[] = hctx <-
    Record[ctx, _] = hctx,
    Context:New[_] = ctx.
```

and add heap context selectively, just to allocations inside factory
methods:

```prolog
Context(ctx) -> .
HeapContext(hctx) -> .

Context:New[heap] = ctx ->
   HeapAllocation(heap), Context(ctx).

HeapContext:New0[] = hctx ->
   HeapContext(hctx).

HeapContext:New1[heap] = hctx ->
   HeapAllocation(heap), HeapContext(hctx).

lang:constructor(`Context:New).
lang:constructor(`HeapContext:New0).
lang:constructor(`HeapContext:New1).

Context:New[heap] = calleeCtx <-
    Merge[_, _, hctx, heap] = calleeCtx,
    HeapContext:New[] = hctx.

# Rule a1
HeapContext:New0[] = hctx <-
    Record[_, heap] = hctx,
    AssignHeapAllocation:Heap[allocinstr] = heap,
    Instruction:Method[allocinstr] = inmethod,
    !FactoryMethod(inmethod).

# Rule a2
HeapContext:New1[lastheap] = hctx <-
    Record[ctx, heap] = hctx,
    AssignHeapAllocation:Heap[allocinstr] = heap,
    Instruction:Method[allocinstr] = inmethod,
    FactoryMethod(inmethod),
    Context:New[lastheap] = ctx.

```

Notice that there are two actual heap context constructors
(`HeapContext:New0` and `HeapContext:New1`) and two corresponding
rules, let's call them `a1` and `a2`, that use these constructors to
create heap contexts. The transformation should take every rule, `r`,
of the program (in the core analysis logic) with `Record` in its head,
and replace `r` with two new rules that are the result of weaving `a1`
and `a2` into `r`.


### Implementation of Macro-Constructors

There are many obvious constraints that the compiler should enforce,
regarding macro-constructors. These come to mind...

For rules that contain a macro-constructor atom in their bodies:

* the head of the rule should contain an actual constructor atom
* this atom and the macro-constructor one should bind the same
  variable, as the returned created entity
* we could even enforce the body of the rule to be an and-expression
  and the head to contain only the constructor atom, just to make the
  transformation easier, even though more flexibility could be
  possible in some cases

For rules that contain a macro-constructor atom in their head:

* the macro-constructor atom should have the same restrictions as if
  it were an ordinary constructor


There is no major challenge in the transformation itself, but rather
at the modularity of the approach. When should this transformation
take place? When compiling a project or lazily at runtime? What if we
add some logic that uses macro constructors, without providing the
actual constructors yet?

The following approach seems to achieve a good compromise:

1. During compilation, we treat macro-constructors as regular
   constructors, but mark them specially.
2. We prohibit the addition of any logic that refers to
   macro-constructors, without first having loaded the logic that
   resolves them to the actual constructors.
3. If we have already loaded such logic, we perform the transformation
   each time we load additional logic that uses (macro-in-head) the
   predefined macro-constructors, so as to completely eliminate them
   from the actual logic to be added to the database.

This way, our primary limitation will be that we'll have to provide
and load definitions for the macro-constructors prior to adding any
more logic---just as, in conventional languages, all symbols have to
be resolved at link-time to produce an executable.


<!-- References and links -->
[Doop]: http://doop.program-analysis.org/
[popl]: https://yanniss.github.io/typesens-popl11.pdf
[popl-slides]: http://www.cse.psu.edu/popl/11/Slides/yannis-popl11.pdf
[algebdt]: https://en.wikipedia.org/wiki/Algebraic_data_type
[cpp]: http://tigcc.ticalc.org/doc/cpp.html
