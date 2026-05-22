---
title: Design
---

# The blog as a place

mkdocs-material is a superb documentation platform. Its defaults are
well-suited to organized, hierarchical reference material. It builds the kind
of site where a reader arrives with a specific question and expects a specific
answer.

Personal blogs aren't really like that. The primary question a visitor
brings is not "where is the thing I need?" but "what has this person been
thinking about lately?" The navigation appropriate for an API reference and
the navigation appropriate for a personal site are not the same thing.

`mkprof init` generates a scaffold that tilts mkdocs-material toward the
second model. Here is what it changes and why.

---

## Posts in the sidebar

The `on_nav` hook in `hooks.py` injects every blog post as a linked item
in the sidebar, directly under the Blog section. It runs after the blog
plugin (at priority −100) so that post URLs are final before the links are
written.

A small script in `docs/javascripts/blog_nav.js` keeps the Blog section
open by default:

```javascript
document$.subscribe(function () {
  document.querySelectorAll(".md-nav__item--nested").forEach(function (item) {
    if (!item.querySelector("a[href$='blog/']")) return;
    var toggle = item.querySelector("input.md-nav__toggle");
    if (toggle && !toggle.checked) toggle.checked = true;
  });
});
```

This sets the checkbox that drives Material's accordion directly. This is
the same mechanism Material's own `navigation.expand` feature uses, just
only for the nav item that contains a link to the blog index. Every other
section is left as-is. The toggle button still renders, so readers who want
to collapse the list can do so. The `document$` observable ensures it fires
on every page transition when `navigation.instant` is enabled, not only on
the initial load.

The reasoning comes from Pirolli and Card's *information foraging* theory
(Xerox PARC, 1999). People navigating the web behave like animals foraging
for food: they follow *information scent*, the cues that suggest a path
toward useful content. A sidebar full of post titles is a rich source of
scent. A visitor who came to read one post can immediately see whether
anything else is worth their time. No searching, recommendation engine.

This is simply what blogs looked like before aggregator apps and
algorithmic feeds took over the job of discovery.

---

## Recent posts on the home page

The `<!-- RECENT_POSTS -->` placeholder in `docs/index.md` is replaced at
build time with the five most recent posts: title, date, and description.

The idea here is Dave Winer's *river of news*, a concept he developed around
2001 while running Scripting News and building what would become RSS. The
premise is that the home page of a personal site is not a static landing
page but a live record of activity. Arriving someone's home page should
answer "what's happening here?"

---

## Working with the grain

Frank Chimero, in *The Web's Grain* (2015), argues that web designers
should work *with* the web's natural texture rather than against it. The
web is fluid, linked, and text-forward. It favors things that flow over
things that are fixed.

So, mkprof doesn't fight mkdocs-material's responsive layout or search.
It ensures that content is discoverable through the site's own navigation,
not only through a search box or an external aggregator.

---

## Recognition over recall

Nielsen and Norman's sixth usability heuristic (1994) states that
interfaces should favor *recognition* over *recall*: people should be
able to identify what they are looking for from visible options rather than
having to remember where it is. A sidebar that lists every post title makes
browsing a recognition task. Hiding posts behind Blog → Archive → 2024
makes it a recall task.

---

## Who is this for

MathJax support, Jupyter notebook conversion, and Obsidian-compatible
frontmatter are not really features most people reach for when they want to
write something. This is aimed at people who write about math, code, and
data, and want to mix those features into their writing naturally rather
that pointing to them.

In other words, this is for folks who read Donald Knuth's *literate programming*
(1984) and didn't think he was crazy, and actually like the idea of interleaving
prose and code into a single document meant to be read by humans first and
executed by machines second. Jupyter notebooks are the direct descendants of that
idea, and the computational notebook is now a primary research artifact across
the quantitative sciences. Given how popular notebooks are these days, I'm frankly
baffled that I even had to write this tool. It seems natural to me to that
notebooks should be blog posts.

In the early 1990s, it was pretty normal in academic circles to run a web servers
on the workstations sitting on your desk. Your publications, datasets, preprints,
and course notes might live at `http://www.cs.university.edu/~name/` — served
directly from the machine used to run the experiments, composed in the same
editor used to write the code. It was a research presence as close to the primary
sources as it was possible to get.

I built mkprof with the hope of reviving that spirit with current tools. You
write and run your notebooks locally, and mkdocs builds the site. The result is a
live extension of the working environment, not a separate content layer you
publish *to*.

---

## What this is not

This is not a replacement for WordPress, Ghost, or Substack. There is no
comment system, no subscriber management, no recommendation engine. It is
closer in spirit to the page a professor served directly from their
SPARCstation than to a Medium publication. The idea is to make the trip
from your research space to the space you share with your community into
something no more disruptive than a trip to the nearest coffee machine.

The opinionated style choices — the dark/light palette toggle, MathJax,
social cards, tags — are all marked `# Style:` in the generated
`mkdocs.yml`. Every one of them can be removed in a minute. The functional
pieces — the nav injection, the recent posts hook, the `attr_list` and
`pymdownx.emoji` extensions — are what make a mkdocs-material site behave
like a *place* rather than a product page.

---

## References

- Pirolli, P. and Card, S. (1999). Information foraging. *Psychological
  Review*, 106(4), 643–675.
- Chimero, F. (2015). [The Web's Grain](https://frankchimero.com/blog/2015/the-webs-grain/).
- Winer, D. (2001). [The River of News](http://scripting.com/davenet/2001/09/29/theRiverOfNewsUiForAggrega.html).
- Nielsen, J. (1994). [10 Usability Heuristics for User Interface Design](https://www.nngroup.com/articles/ten-usability-heuristics/).
- Knuth, D. (1984). Literate programming. *The Computer Journal*, 27(2), 97–111.
