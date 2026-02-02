export function cx(...classes: Array<string | undefined | false>) {
  return classes.filter(Boolean).join(" ");
}
