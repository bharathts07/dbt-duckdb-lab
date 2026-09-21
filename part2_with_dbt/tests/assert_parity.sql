-- Both pipelines must agree on clean data. If this fails, one of them has a
-- bug, and finding out which is a better lesson than either working first time.
with a as (select revenue_date, source_system, order_count,
                  round(revenue_usd,2) as revenue_usd from built_by_hand.revenue_per_day),
     b as (select revenue_date, source_system, order_count,
                  round(revenue_usd,2) as revenue_usd from {{ ref('revenue_per_day') }})
select 'part1_only' as side, * from (select * from a except select * from b)
union all
select 'part2_only' as side, * from (select * from b except select * from a)
