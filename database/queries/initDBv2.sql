SET check_function_bodies = false
;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE public.actions(
  id serial PRIMARY KEY,
  player_id uuid NOT NULL,
  category integer NOT NULL,
  "object" text NOT NULL,
  "value" integer NOT NULL,
  CONSTRAINT unique_action UNIQUE (player_id, "object", category)
);

COMMENT ON TABLE public.actions IS
  'Stores all the relevant data regarding the player statistics.
In  "uuid" is the player stored
in "object" it is stated what the other data refers to (stone_block, diamond_sword, zombie,....)
in "category" is stated in which context the item should be interpretet (mined blocks, collected blocks, item usage, killed mobs, ....)
"value" is the corresponding value '
  ;

CREATE TABLE public.ban_reasons(
  reason text NOT NULL, 
  ban_duration_in_days integer NOT NULL,
  id SERIAL NOT NULL,
  CONSTRAINT ban_reasons_pkey PRIMARY KEY(id),
  CONSTRAINT ban_reasons_key UNIQUE(reason)
);

CREATE TABLE public.banned_players(
  id serial NOT NULL,
  banned_player_id uuid NOT NULL,
  moderator_id uuid NOT NULL,
  ban_reason_id integer NOT NULL,
  "comment" text,
  ban_start timestamp without time zone NOT NULL,
  ban_end timestamp without time zone NOT NULL,
  CONSTRAINT banned_players_pkey PRIMARY KEY(id)
);

COMMENT ON TABLE public.banned_players IS
  'Contains the uuids and informations about banned players';

CREATE TABLE public.block_lookup(
  id serial NOT NULL, 
  blocks text NOT NULL,
  CONSTRAINT block_lookup_pkey PRIMARY KEY(id)
);
CREATE UNIQUE INDEX block_lookup_index
ON public.block_lookup(blocks);

CREATE TABLE public.email_verification(
  id integer NOT NULL,
  verification_code integer NOT NULL,
  verification_timestamp timestamp without time zone NOT NULL,
  CONSTRAINT email_verification_pkey PRIMARY KEY(id)
);

CREATE TABLE public.item_lookup(
  id serial NOT NULL, 
  items text NOT NULL,
  CONSTRAINT item_lookup_pkey PRIMARY KEY(id)
);
CREATE UNIQUE INDEX item_lookup_index
ON public.item_lookup(items);

CREATE TABLE public.login(
  id serial NOT NULL,
  player_id uuid NOT NULL,
  pin integer NOT NULL,
  "timestamp" timestamp without time zone NOT NULL,
  CONSTRAINT login_pkey PRIMARY KEY(id),
  CONSTRAINT player_id_ukey UNIQUE(player_id)
);

COMMENT ON TABLE public.login IS
  'Stores the pin the player is required to provide on login';

CREATE TABLE public.player(
uuid uuid NOT NULL, "name" text NOT NULL,
  CONSTRAINT player_pkey PRIMARY KEY(uuid)
);

CREATE TABLE public.player_prefixes(
  id serial PRIMARY KEY,  
  player_id uuid NOT NULL
);

CREATE TABLE public.player_server_info(
  player_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  player_uuid uuid NOT NULL,
  server_id integer NOT NULL,
  online boolean NOT NULL,
  first_seen timestamp without time zone NOT NULL,
  last_seen timestamp without time zone NOT NULL,
  web_access_permissions smallint NOT NULL,
  CONSTRAINT player_server_info_pkey PRIMARY KEY(player_id),
  CONSTRAINT player_server_info_server_player_unique UNIQUE (server_id, player_uuid),
  CONSTRAINT player_server_info_key UNIQUE(player_uuid)
);

COMMENT ON TABLE public.player_server_info IS
  'Saves player data regarding the online status, last seen,...';

CREATE TABLE public.prefixes(
  prefix_id serial NOT NULL,
  prefix_owner_id uuid NOT NULL,
  prefix_text text NOT NULL,
  "password" text,
  CONSTRAINT prefixes_pkey PRIMARY KEY(prefix_owner_id, prefix_id)
);

CREATE TABLE public."servers"(
  id serial PRIMARY KEY,
  "owner" text NOT NULL,
  subdomain text NOT NULL,
  mc_server_domain text NOT NULL,
  discord_url text NOT NULL,
  server_description_short text NOT NULL,
  server_description_long text NOT NULL,
  server_name text NOT NULL,
  server_key character(64) NOT NULL,
  CONSTRAINT "owner" UNIQUE(owner),
  CONSTRAINT subdomain UNIQUE(subdomain),
  CONSTRAINT server_key UNIQUE(server_key),
  CONSTRAINT mc_server_domain UNIQUE(mc_server_domain),
  CONSTRAINT server_name UNIQUE(server_name)
);

CREATE TABLE public."server_admins"(
  username text NOT NULL,
  email text NOT NULL,
  "password" text NOT NULL,
  license_type integer NOT NULL,
  email_verified bool NOT NULL,
  minecraft_account_uuid uuid,
  verification_process_id SERIAL,
  CONSTRAINT "server_admins_pkey" PRIMARY KEY(username),
  CONSTRAINT "server_admins_key" UNIQUE(verification_process_id),
  CONSTRAINT "server_admins_key1" UNIQUE(email)
);

ALTER TABLE public.actions
  ADD CONSTRAINT actions_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES public.player_server_info (player_id)
      ON DELETE No action ON UPDATE No action;

ALTER TABLE public.banned_players
  ADD CONSTRAINT banned_players_banned_player_id_fkey
    FOREIGN KEY (banned_player_id) REFERENCES public.player_server_info (player_id)
      ON DELETE No action ON UPDATE No action;

ALTER TABLE public.login
  ADD CONSTRAINT login_player_id_fkey
    FOREIGN KEY (player_id) REFERENCES public.player_server_info (player_id)
      ON DELETE No action ON UPDATE No action;

ALTER TABLE public.player_server_info
  ADD CONSTRAINT player_server_info_player_uuid_fkey
    FOREIGN KEY (player_uuid) REFERENCES public.player (uuid) ON DELETE No action
      ON UPDATE No action;

ALTER TABLE public.player_server_info
  ADD CONSTRAINT player_server_info_server_id_fkey
    FOREIGN KEY (server_id) REFERENCES public."servers" (id) ON DELETE No action
      ON UPDATE No action;

ALTER TABLE public.player_prefixes
  ADD CONSTRAINT player_prefixes_player_id_fkey1
    FOREIGN KEY (player_id) REFERENCES public.player_server_info (player_id);

ALTER TABLE public.prefixes
  ADD CONSTRAINT prefix_id FOREIGN KEY (prefix_id) REFERENCES public.player_prefixes (id);

ALTER TABLE public.player_prefixes ADD CONSTRAINT unique_prefix_id UNIQUE (id);

ALTER TABLE public.prefixes
  ADD CONSTRAINT prefixes_prefix_owner_id_fkey
    FOREIGN KEY (prefix_owner_id) REFERENCES public.player_server_info (player_id);

ALTER TABLE public."server_admins"
  ADD CONSTRAINT "server_admins_minecraft_account_uuid_fkey"
    FOREIGN KEY (minecraft_account_uuid)
      REFERENCES public.player_server_info (player_uuid);

ALTER TABLE public."server_admins"
  ADD CONSTRAINT "server_admins_username_fkey"
    FOREIGN KEY (username) REFERENCES public."servers" ("owner");

ALTER TABLE public.email_verification
  ADD CONSTRAINT email_verification_id_fkey
    FOREIGN KEY (id) REFERENCES public."server_admins" (verification_process_id);

ALTER TABLE public.banned_players
  ADD CONSTRAINT banned_players_moderator_id_fkey
    FOREIGN KEY (moderator_id) REFERENCES public.player_server_info (player_id);

ALTER TABLE public.banned_players
  ADD CONSTRAINT ban_reasons_id_fkey
    FOREIGN KEY (ban_reason_id) REFERENCES public.ban_reasons (id);

CREATE INDEX player_uuid_idx ON public.player(uuid);
CREATE INDEX player_server_info_player_uuid_idx ON public.player_server_info(player_uuid);
CREATE INDEX servers_id_idx ON public."servers" (id);

