SET check_function_bodies = false
;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE public.player(
  uuid uuid NOT NULL, "name" text NOT NULL,
  CONSTRAINT player_pkey PRIMARY KEY(uuid)
);

CREATE TABLE public."servers"(
  id serial PRIMARY KEY,
  "owner_id" int NOT NULL,
  subdomain text NOT NULL,
  mc_server_domain text NOT NULL,
  discord_url text,
  server_description_short text NOT NULL,
  server_description_long text NOT NULL,
  server_name text NOT NULL,
  server_key character(64) NOT NULL,
  license_type integer NOT NULL DEFAULT 0,
  created_at timestamp NOT NULL DEFAULT NOW(),
  CONSTRAINT "owner_pkey" UNIQUE(owner_id),
  CONSTRAINT subdomain UNIQUE(subdomain),
  CONSTRAINT server_key UNIQUE(server_key),
  CONSTRAINT mc_server_domain UNIQUE(mc_server_domain),
  CONSTRAINT server_name UNIQUE(server_name)
);

CREATE TABLE public.prefixes(
  prefix_id serial NOT NULL UNIQUE,
  prefix_owner_id uuid NOT NULL,
  prefix_text text NOT NULL,
  "password" text,
  CONSTRAINT prefixes_pkey PRIMARY KEY(prefix_owner_id, prefix_id)
);

CREATE TABLE public.player_server_info(
  player_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  mojang_uuid UUID NOT NULL,
  server_id INT NOT NULL REFERENCES servers(id),
  "online" boolean NOT NULL DEFAULT false,
  first_seen timestamp without time zone,
  last_seen timestamp without time zone,
  prefix_id int REFERENCES prefixes(prefix_id),

  web_access_permissions smallint NOT NULL,
  created_at timestamp NOT NULL DEFAULT NOW(),
  CONSTRAINT player_server_info_server_player_unique UNIQUE (server_id, mojang_uuid)
);
ALTER TABLE player_server_info ADD CONSTRAINT player_server_info_mojang_uuid_key UNIQUE (mojang_uuid);
CREATE TABLE public.actions(
  id serial PRIMARY KEY,
  player_id uuid NOT NULL,
  category integer NOT NULL,
  "object" text NOT NULL,
  "value" integer NOT NULL,
  CONSTRAINT unique_action UNIQUE (player_id, "object", category)
);

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


CREATE TABLE public.block_lookup(
  id serial NOT NULL, 
  blocks text NOT NULL,
  CONSTRAINT block_lookup_pkey PRIMARY KEY(id)
);


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


CREATE TABLE public.login(
  id serial NOT NULL,
  player_id uuid NOT NULL,
  pin integer NOT NULL,
  "timestamp" timestamp without time zone NOT NULL,
  CONSTRAINT login_pkey PRIMARY KEY(id),
  CONSTRAINT player_id_ukey UNIQUE(player_id)
);


CREATE TABLE public."server_admins"(
  id serial NOT NULL,
  username text NOT NULL,
  email text NOT NULL,
  "password" text NOT NULL,
  email_verified bool NOT NULL,
  verification_process_id SERIAL,
  created_at timestamp NOT NULL DEFAULT NOW(),

  CONSTRAINT "server_admins_pkey" PRIMARY KEY(id),
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


ALTER TABLE public.servers
  ADD CONSTRAINT "owner_id_fkey"
    FOREIGN KEY ("owner_id") REFERENCES public.server_admins (id);


ALTER TABLE public.prefixes
  ADD CONSTRAINT prefixes_prefix_owner_id_fkey
    FOREIGN KEY (prefix_owner_id) REFERENCES public.player_server_info (player_id);



ALTER TABLE public.email_verification
  ADD CONSTRAINT email_verification_id_fkey
    FOREIGN KEY (id) REFERENCES public."server_admins" (verification_process_id);

ALTER TABLE public.banned_players
  ADD CONSTRAINT banned_players_moderator_id_fkey
    FOREIGN KEY (moderator_id) REFERENCES public.player_server_info (player_id);

ALTER TABLE public.banned_players
  ADD CONSTRAINT ban_reasons_id_fkey
    FOREIGN KEY (ban_reason_id) REFERENCES public.ban_reasons (id);


ALTER TABLE public.player_server_info
  ADD CONSTRAINT player_server_info_mojang_uuid_fkey
    FOREIGN KEY (mojang_uuid) REFERENCES public.player (uuid)
  ON DELETE NO ACTION
  ON UPDATE NO ACTION;


CREATE INDEX player_uuid_idx ON public.player(uuid);
CREATE INDEX player_server_info_player_uuid_idx ON public.player_server_info(mojang_uuid);
CREATE INDEX servers_id_idx ON public."servers" (id);
CREATE INDEX ON banned_players(banned_player_id);
CREATE INDEX ON banned_players(moderator_id);
CREATE INDEX ON actions(player_id);
CREATE INDEX ON player_server_info(server_id);
CREATE UNIQUE INDEX block_lookup_index ON public.block_lookup(blocks);
CREATE UNIQUE INDEX item_lookup_index ON public.item_lookup(items);

COMMENT ON TABLE public.banned_players IS
  'Contains the uuids and informations about banned players';

COMMENT ON TABLE public.actions IS
  'Stores all the relevant data regarding the player statistics.
In  "uuid" is the player stored
in "object" it is stated what the other data refers to (stone_block, diamond_sword, zombie,....)
in "category" is stated in which context the item should be interpretet (mined blocks, collected blocks, item usage, killed mobs, ....)
"value" is the corresponding value '
  ;
COMMENT ON TABLE public.login IS
  'Stores the pin the player is required to provide on login';
COMMENT ON TABLE public.player_server_info IS
  'Saves player data regarding the online status, last seen,...';

