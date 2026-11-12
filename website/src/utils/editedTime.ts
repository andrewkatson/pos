/**
 * Whether an edit saved on this screen (issue #462) is still newer than
 * content just fetched from the server. A fetch whose request went out before
 * the save can land after it with the old text; its edited_time is older (or
 * absent), so the saved edit should keep showing. A fetch that already carries
 * this edit, or a later one made on another device, is at least as new and
 * wins.
 */
export function savedEditIsNewer(
  savedEditedTime: string | null | undefined,
  fetchedEditedTime: string | null | undefined,
): boolean {
  if (!savedEditedTime) return false
  if (!fetchedEditedTime) return true
  return Date.parse(fetchedEditedTime) < Date.parse(savedEditedTime)
}
