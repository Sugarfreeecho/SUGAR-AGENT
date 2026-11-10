/**
 * Sidebar favourites are a first-level directory: favourited sessions leave the
 * normal time / workdir groups and appear only in `sections.favorites`.
 *
 * Run: node tests/session-favorites.test.mjs
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../src/app/state/session-selectors.js', import.meta.url), 'utf8');
const sessions = [
    { id: 'favorite', name: 'Favorite', favorite: true, pinned: true, last_activity_at: '2026-11-01T00:00:00Z' },
    { id: 'normal', name: 'Normal', last_activity_at: '2026-11-02T00:00:00Z' },
    { id: 'archived-favorite', name: 'Archived favorite', favorite: true, archived: true, last_activity_at: '2026-10-01T00:00:00Z' },
];
const context = vm.createContext({
    console,
    sessionStore: {
        list: () => sessions,
        archivedList: () => [sessions[2]],
        archivedCount: 1,
    },
    localStorage: { getItem: () => null, setItem: () => {} },
    document: {},
    window: {},
});
vm.runInContext(source, context);

const ids = (list) => list.map((session) => session.id);
const sections = context.selectSessionSections();
assert.equal(ids(sections.favorites).join(','), 'favorite');
assert.equal(ids(sections.normal).join(','), 'normal');
assert.equal(sections.showFavoritesSection, true);
assert.equal(
    sections.normalGroups.some((group) => group.sessions.some((session) => session.id === 'favorite')),
    false,
    'a favourite must not be repeated in the normal time groups',
);
assert.equal(
    sections.favorites.some((session) => session.id === 'archived-favorite'),
    false,
    'an archived favourite stays in the archive directory',
);

context.setSessionListSearchQuery('normal');
const filtered = context.selectSessionSections();
assert.equal(ids(filtered.favorites).join(','), '');
assert.equal(ids(filtered.normal).join(','), 'normal');

console.log('Session favourites: first-level partition, archive exclusion and sidebar search passed.');
