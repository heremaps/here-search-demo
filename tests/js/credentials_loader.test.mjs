import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const {
  parseProps,
  normalizeCredentials,
  isValidCredentials,
  hasValidActiveConfig,
} = require("../../src/here_search_demo/widgets/js/credentials_loader_logic.js");

var assert = {
  equal: function (left, right) {
    if (left !== right) {
      throw new Error("Assertion failed: expected " + JSON.stringify(right) + " but got " + JSON.stringify(left));
    }
  },
};

function run(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    console.error(error);
    process.exitCode = 1;
  }
}

run("parseProps handles properties and comments", () => {
  const parsed = parseProps(`
# comment
here.access.key.id = id-123
apiKey = api-123
`);

  assert.equal(parsed["here.access.key.id"], "id-123");
  assert.equal(parsed.apikey, "api-123");
});

run("normalizeCredentials maps apiKey fallback", () => {
  const normalized = normalizeCredentials({ apikey: "abc" });
  assert.equal(normalized["here.api.key"], "abc");
});

run("isValidCredentials accepts complete credentials with apiKey", () => {
  const valid = isValidCredentials(`
here.token.endpoint.url=https://token.example.com
here.access.key.id=id
here.access.key.secret=secret
apiKey=api
`);

  assert.equal(valid, true);
});

run('isValidCredentials rejects placeholder value "..."', () => {
  const valid = isValidCredentials(`
here.token.endpoint.url=https://token.example.com
here.access.key.id=...
here.access.key.secret=secret
here.api.key=api
`);

  assert.equal(valid, false);
});

run("hasValidActiveConfig accepts complete active_config", () => {
  const valid = hasValidActiveConfig({
    "here.token.endpoint.url": "https://token.example.com",
    "here.access.key.id": "id",
    "here.access.key.secret": "secret",
    "here.api.key": "api",
  });

  assert.equal(valid, true);
});

run('hasValidActiveConfig rejects placeholder "..." in active_config', () => {
  const valid = hasValidActiveConfig({
    "here.token.endpoint.url": "https://token.example.com",
    "here.access.key.id": "id",
    "here.access.key.secret": "...",
    "here.api.key": "api",
  });

  assert.equal(valid, false);
});

run("hasValidActiveConfig rejects missing key in active_config", () => {
  const valid = hasValidActiveConfig({
    "here.token.endpoint.url": "https://token.example.com",
    "here.access.key.id": "id",
    "here.access.key.secret": "secret",
  });

  assert.equal(valid, false);
});
