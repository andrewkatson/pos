import '@testing-library/jest-dom/vitest'

// jsdom has no layout engine, so it does not implement scrollIntoView. The post
// detail page calls it to bring a shared `#comment-<id>` into view (issue #381);
// without a stub the call throws and takes the whole render down.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
