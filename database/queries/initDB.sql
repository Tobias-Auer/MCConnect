SET check_function_bodies = false
;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE public.player(
  uuid uuid NOT NULL,
  "name" text NOT NULL,
  CONSTRAINT player_key UNIQUE(uuid),
  CONSTRAINT player_pkey PRIMARY KEY(uuid)
);

CREATE TABLE public."server"(
  server_id SERIAL,
  subdomain text NOT NULL,
  license_type integer NOT NULL,
  owner_name text,
  mc_server_domain text,
  CONSTRAINT server_key UNIQUE(server_id),
  CONSTRAINT server_pkey PRIMARY KEY(server_id)
);

CREATE TABLE public.player_server_info(
  id uuid NOT NULL,
  server_id integer NOT NULL,
  player_uuid uuid NOT NULL,
  online boolean NOT NULL,
  first_seen timestamp without time zone NOT NULL,
  last_seen timestamp without time zone NOT NULL,
  web_access_permissions smallint NOT NULL,
  CONSTRAINT player_server_info_server_player_unique UNIQUE(server_id, player_uuid),
  CONSTRAINT player_server_info_pkey PRIMARY KEY(id)
);

COMMENT ON TABLE public.player_server_info IS
  'Saves player data regarding the online status, last seen,...';

CREATE TABLE public.actions(
  id integer NOT NULL,
  player_id uuid NOT NULL,
  "object" text NOT NULL,
  category smallint NOT NULL,
  "value" integer NOT NULL,
  CONSTRAINT actions_pkey PRIMARY KEY(id)
);

COMMENT ON COLUMN public.actions.category IS
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

COMMENT ON TABLE public.actions IS
  'Stores all the relevant data regarding the player statistics.
In  "uuid" is the player stored
in "object" it is stated what the other data refers to (stone_block, diamond_sword, zombie,....)
in "category" is stated in which context the item should be interpretet (mined blocks, collected blocks, item usage, killed mobs, ....)
"value" is the corresponding value '
  ;

CREATE TABLE public.banned_players(
  id SERIAL,
  player_id uuid NOT NULL,
  "admin" uuid NOT NULL,
  ban_reason text NOT NULL,
  ban_start timestamp without time zone NOT NULL,
  ban_end timestamp without time zone NOT NULL,
  CONSTRAINT banned_players_pkey PRIMARY KEY(id)
);

COMMENT ON TABLE public.banned_players IS
  'Contains the uuids and informations about banned players';

CREATE TABLE public.login(
  id SERIAL,
  player_id uuid NOT NULL,
  pin integer NOT NULL,
  "timestamp" timestamp without time zone NOT NULL,
  CONSTRAINT login_pkey PRIMARY KEY(id)
);

COMMENT ON TABLE public.login IS
  'Stores the pin the player is required to provide on login';

CREATE TABLE public.player_prefixes(
  id SERIAL,
  player_id uuid NOT NULL,
  prefix text,
  "password" text,
  members uuid[],
  CONSTRAINT player_prefixes_pkey PRIMARY KEY(id)
);

COMMENT ON TABLE public.player_prefixes IS
  'The prefix which a player can configure on the website';

ALTER TABLE public.actions
  ADD CONSTRAINT actions_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES public.player_server_info (id)
      ON DELETE No action ON UPDATE No action;

ALTER TABLE public.banned_players
  ADD CONSTRAINT banned_players_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES public.player_server_info (id)
      ON DELETE No action ON UPDATE No action;

ALTER TABLE public.login
  ADD CONSTRAINT login_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES public.player_server_info (id)
      ON DELETE No action ON UPDATE No action;

ALTER TABLE public.player_prefixes
  ADD CONSTRAINT player_prefixes_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES public.player_server_info (id)
      ON DELETE No action ON UPDATE No action;

ALTER TABLE public.player_server_info
  ADD CONSTRAINT player_server_info_player_uuid_fkey
    FOREIGN KEY (player_uuid) REFERENCES public.player (uuid) ON DELETE No action
      ON UPDATE No action;

ALTER TABLE public.player_server_info
  ADD CONSTRAINT player_server_info_server_id_fkey
    FOREIGN KEY (server_id) REFERENCES public."server" (server_id)
      ON DELETE No action ON UPDATE No action;
