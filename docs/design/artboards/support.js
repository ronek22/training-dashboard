// Minimal standalone renderer for the exported design-canvas artboards (*.dc.html).
// Supports <helmet>, <sc-for list as>, <sc-if value>, {{path}} in text/attributes and the
// <script type="text/x-dc"> Component.renderVals() data block. Static preview only (no interactions).
window.DCLogic = class { constructor () { this.state = {}; this.props = {} } setState (s) { Object.assign(this.state, s) } };
(function () {
  const RE = /{{\s*([^}]+?)\s*}}/g;
  const lookup = (expr, scopes) => {
    expr = expr.trim();
    if (expr === 'true') return true; if (expr === 'false') return false;
    if (/^-?\d+(\.\d+)?$/.test(expr)) return Number(expr);
    const parts = expr.split('.');
    for (let i = scopes.length - 1; i >= 0; i--) {
      if (scopes[i] && parts[0] in Object(scopes[i])) return parts.reduce((v, k) => (v == null ? v : v[k]), scopes[i]);
    }
    return undefined;
  };
  const interp = (str, scopes) => str.replace(RE, (_, e) => { const v = lookup(e, scopes); return v == null ? '' : String(v) });
  const single = (str, scopes) => { const m = str && str.match(/^\s*{{\s*([^}]+?)\s*}}\s*$/); return m ? lookup(m[1], scopes) : str };
  function render (node, scopes) {
    for (const child of [...node.childNodes]) {
      if (child.nodeType === 3) { if (RE.test(child.data)) child.data = interp(child.data, scopes); RE.lastIndex = 0; continue }
      if (child.nodeType !== 1) continue;
      const tag = child.localName;
      if (tag === 'sc-for') {
        const list = single(child.getAttribute('list'), scopes) || [];
        const as = child.getAttribute('as') || 'item';
        const frag = document.createDocumentFragment();
        list.forEach((item, index) => {
          const holder = child.cloneNode(true);
          render(holder, [...scopes, { [as]: item, index }]);
          while (holder.firstChild) frag.appendChild(holder.firstChild);
        });
        child.replaceWith(frag);
      } else if (tag === 'sc-if') {
        if (single(child.getAttribute('value'), scopes)) {
          render(child, scopes);
          const frag = document.createDocumentFragment();
          while (child.firstChild) frag.appendChild(child.firstChild);
          child.replaceWith(frag);
        } else child.remove();
      } else {
        for (const attr of [...child.attributes]) if (attr.value.includes('{{')) child.setAttribute(attr.name, interp(attr.value, scopes));
        render(child, scopes);
      }
    }
  }
  function boot () {
    const root = document.querySelector('x-dc'); if (!root) return;
    const helmet = root.querySelector('helmet');
    if (helmet) { [...helmet.childNodes].forEach((n) => document.head.appendChild(n)); helmet.remove() }
    let vals = {};
    const script = document.querySelector('script[type="text/x-dc"]');
    if (script) {
      try { const Component = new Function('DCLogic', script.textContent + '\nreturn Component;')(window.DCLogic); vals = new Component().renderVals() || {} } catch (e) { console.error('artboard data script failed', e) }
    }
    render(root, [vals]);
    document.documentElement.dataset.rendered = '1';
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
