/** Concatena classes ignorando `false`, `null` e `undefined`. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
