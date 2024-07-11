SET check_function_bodies = false
;

CREATE TABLE actions(
  id integer NOT NULL,
  player_id integer NOT NULL,
  "object" text NOT NULL,
  category smallint NOT NULL,
  "value" integer NOT NULL,
  CONSTRAINT actions_pkey PRIMARY KEY(id)
);

COMMENT ON COLUMN actions.category IS
  'what type of item is it?
A block? A tool? A pickable item? A mob? 
Also block mined, block collected, block crafted.... Mob killed or killed by mob,.....
1: Blocks mined
2: Blocks collected
3: Blocks dropped
4: Blocks crafted
5: tool crafted
6: tool used
7: Killed Mob
8: Killed by mob
...
...'
  ;

COMMENT ON TABLE actions IS
  'Stores all the relevant data regarding the player statistics.
In  "uuid" is the player stored
in "object" it is stated what the other data refers to (stone_block, diamond_sword, zombie,....)
in "category" is stated in which context the item should be interpretet (mined blocks, collected blocks, item usage, killed mobs, ....)
"value" is the corresponding value '
  ;

CREATE TABLE banned_players(
  id integer NOT NULL,
  player_id integer,
  "admin" integer NOT NULL,
  ban_reason text NOT NULL,
  ban_start timestamp NOT NULL,
  ban_end timestamp NOT NULL
);

COMMENT ON TABLE banned_players IS
  'Contains the uuids and informations about banned players';

CREATE TABLE login(
  id integer NOT NULL,
  player_id integer NOT NULL,
  pin integer NOT NULL,
  "timestamp" timestamp NOT NULL,
  CONSTRAINT login_pkey PRIMARY KEY(id)
);

COMMENT ON TABLE login IS
  'Stores the pin the player is required to provide on login';

CREATE TABLE player(
  id integer NOT NULL,
  uuid integer NOT NULL,
  "name" text NOT NULL,
  CONSTRAINT player_pkey1 PRIMARY KEY(id)
);

CREATE TABLE player_prefixes(
  id integer NOT NULL,
  player_id integer NOT NULL,
  prefix text,
  "password" text,
  members integer
);

COMMENT ON TABLE player_prefixes IS
  'The prefix which a player can configure on the website';

CREATE TABLE player_server_info(
  id integer NOT NULL,
  server_id integer NOT NULL,
  player_uuid integer NOT NULL,
  online bit NOT NULL,
  first_seen timestamp NOT NULL,
  last_seen timestamp NOT NULL,
  web_access_permissions smallint NOT NULL,
  CONSTRAINT player_server_info_pkey PRIMARY KEY(id),
  CONSTRAINT player_server_info_key UNIQUE(server_id),
  CONSTRAINT player_server_info_key1 UNIQUE(player_uuid)
);

COMMENT ON TABLE player_server_info IS
  'Saves player data regarding the online status, last seen,...';

CREATE TABLE "server"(
  id integer NOT NULL,
  server_id integer NOT NULL,
  subdomain text NOT NULL,
  owner_name text,
  mc_server_domain text,
  CONSTRAINT server_pkey PRIMARY KEY(id)
);

ALTER TABLE actions
  ADD CONSTRAINT actions_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES player_server_info (id);

ALTER TABLE banned_players
  ADD CONSTRAINT banned_players_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES player_server_info (id);

ALTER TABLE login
  ADD CONSTRAINT login_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES player_server_info (id);

ALTER TABLE player_prefixes
  ADD CONSTRAINT player_prefixes_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES player_server_info (id);

ALTER TABLE player
  ADD CONSTRAINT player_uuid_fkey
    FOREIGN KEY (uuid) REFERENCES player_server_info (player_uuid);

ALTER TABLE "server"
  ADD CONSTRAINT server_server_id_fkey
    FOREIGN KEY (server_id) REFERENCES player_server_info (server_id);
