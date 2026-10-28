// Reserve the space after the grid once, so scrolling never resizes the photo.
export function mountStickyPhotoLayout(host) {
  const view = host.ownerDocument?.defaultView;
  if (!view?.requestAnimationFrame) return () => {};
  let pending = false;
  const update = () => {
    pending = false;
    const grid = host.querySelector('.quick-columns');
    const photo = grid?.querySelector('.quick-strip');
    if (!photo) return;
    const top = parseFloat(view.getComputedStyle(photo).top) || 0;
    const gridBottom = grid.getBoundingClientRect().bottom + view.scrollY;
    const trailingSpace = Math.max(0, Math.ceil(host.ownerDocument.documentElement.scrollHeight - gridBottom));
    const available = Math.max(1, Math.floor(view.innerHeight - top - trailingSpace - 12));
    const value = `${available}px`;
    if (photo.style.getPropertyValue('--quick-photo-available-height') !== value)
      photo.style.setProperty('--quick-photo-available-height', value);
  };
  const schedule = () => {
    if (pending) return;
    pending = true;
    view.requestAnimationFrame(update);
  };
  view.addEventListener('resize', schedule);
  if (view.ResizeObserver) new view.ResizeObserver(schedule).observe(host);
  schedule();
  return schedule;
}
