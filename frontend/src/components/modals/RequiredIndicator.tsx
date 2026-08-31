/** Decorative required-field marker; native form validation remains the semantic authority. */
export function RequiredIndicator() {
  return (
    <span
      aria-hidden="true"
      data-required-indicator="true"
      style={{ color: 'var(--color-danger)' }}
    >
      *
    </span>
  );
}
